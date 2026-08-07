# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""Pure-numpy TFLite interpreter fallback.

Supports a fixed subset of ops:
  SHAPE, STRIDED_SLICE, PACK, RESHAPE, MEAN,
  CONV_2D, DEPTHWISE_CONV_2D, AVERAGE_POOL_2D,
  FULLY_CONNECTED, SOFTMAX

Intended for platforms where tflite-runtime is unavailable.
All arithmetic is done in float32 (dequantise → compute → requantise).
Per-channel quantisation on weights is fully supported.
"""

from __future__ import annotations

import numpy as np

try:
    import flatbuffers  # noqa: F401
    from tflite.Model import Model
    from tflite.BuiltinOperator import BuiltinOperator
    from tflite.Padding import Padding as TFLPadding
    from tflite.ActivationFunctionType import ActivationFunctionType
    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False


def _same_padding(in_h, in_w, kH, kW, stride_h, stride_w):
    """Return (pad_top, pad_bottom, pad_left, pad_right) for SAME padding."""
    out_h = (in_h + stride_h - 1) // stride_h
    out_w = (in_w + stride_w - 1) // stride_w
    pad_h = max((out_h - 1) * stride_h + kH - in_h, 0)
    pad_w = max((out_w - 1) * stride_w + kW - in_w, 0)
    return pad_h // 2, pad_h - pad_h // 2, pad_w // 2, pad_w - pad_w // 2


def _clip_activation(x: np.ndarray, activation: int) -> np.ndarray:
    if activation == ActivationFunctionType.RELU:
        return np.maximum(x, 0.0)
    if activation == ActivationFunctionType.RELU6:
        return np.clip(x, 0.0, 6.0)
    if activation == ActivationFunctionType.RELU_N1_TO_1:
        return np.clip(x, -1.0, 1.0)
    return x


def _quantize_i8(x_f32: np.ndarray, scale: float, zero_point: int) -> np.ndarray:
    return np.clip(np.round(x_f32 / scale + zero_point), -128, 127).astype(np.int8)


class Interpreter:
    """Minimal TFLite interpreter implemented with NumPy."""

    def __init__(self, model_path: str | None = None, model_content: bytes | None = None):
        if not _DEPS_OK:
            raise ImportError(
                "tflite_numpy_interpreter requires 'flatbuffers' and 'tflite' packages. "
                "Install them with: pip install flatbuffers tflite"
            )
        if model_content is not None:
            buf = bytearray(model_content)
        elif model_path is not None:
            with open(model_path, "rb") as f:
                buf = bytearray(f.read())
        else:
            raise ValueError("model_path or model_content is required")

        self._buf = buf
        self._model = Model.GetRootAs(buf, 0)
        self._tensor_meta: dict = {}
        self._tensor_data: dict = {}
        self._ops: list = []
        self._input_indices: list[int] = []
        self._output_indices: list[int] = []
        self._allocated = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allocate_tensors(self) -> None:
        model = self._model
        subgraph = model.Subgraphs(0)

        dtype_map = {0: np.float32, 2: np.int32, 3: np.uint8, 9: np.int8}

        for i in range(subgraph.TensorsLength()):
            t = subgraph.Tensors(i)
            q = t.Quantization()
            shape = [t.Shape(j) for j in range(t.ShapeLength())]
            dtype = dtype_map.get(t.Type(), np.float32)

            if q and q.ScaleLength() > 0:
                scales = np.array([q.Scale(j) for j in range(q.ScaleLength())], dtype=np.float32)
                zps = np.array([q.ZeroPoint(j) for j in range(q.ZeroPointLength())], dtype=np.int32)
                scale = float(scales[0]) if len(scales) == 1 else scales
                zp = int(zps[0]) if len(zps) == 1 else zps
                quant_dim = int(q.QuantizedDimension()) if len(scales) > 1 else 0
            else:
                scale, zp, quant_dim = 1.0, 0, 0

            self._tensor_meta[i] = {
                "index": i,
                "shape": shape,
                "dtype": dtype,
                "scale": scale,
                "zero_point": zp,
                "quantization": (scale, zp),
                "quantized_dimension": quant_dim,
            }

        # Load constant tensors (weights / biases) from flatbuffer buffers
        for i in range(subgraph.TensorsLength()):
            t = subgraph.Tensors(i)
            buf_idx = t.Buffer()
            if buf_idx > 0:
                fb = model.Buffers(buf_idx)
                if fb.DataLength() > 0:
                    raw = fb.DataAsNumpy()  # uint8 view of buffer bytes
                    info = self._tensor_meta[i]
                    arr = raw.view(info["dtype"]).reshape(info["shape"])
                    self._tensor_data[i] = arr.copy()
                else:
                    self._tensor_data[i] = None
            else:
                self._tensor_data[i] = None

        # Parse ops
        op_codes = {v: k for k, v in vars(BuiltinOperator).items() if not k.startswith("_")}
        for i in range(subgraph.OperatorsLength()):
            op = subgraph.Operators(i)
            code = model.OperatorCodes(op.OpcodeIndex()).BuiltinCode()
            name = op_codes.get(code, f"UNKNOWN_{code}")
            ins = [op.Inputs(j) for j in range(op.InputsLength())]
            outs = [op.Outputs(j) for j in range(op.OutputsLength())]
            opts = self._parse_options(op, code)
            self._ops.append((name, ins, outs, opts))

        self._input_indices = [subgraph.Inputs(i) for i in range(subgraph.InputsLength())]
        self._output_indices = [subgraph.Outputs(i) for i in range(subgraph.OutputsLength())]
        self._allocated = True

    def get_input_details(self) -> list[dict]:
        return [self._tensor_meta[i] for i in self._input_indices]

    def get_output_details(self) -> list[dict]:
        return [self._tensor_meta[i] for i in self._output_indices]

    def set_tensor(self, tensor_index: int, value) -> None:
        self._tensor_data[tensor_index] = np.array(value, dtype=self._tensor_meta[tensor_index]["dtype"])

    def get_tensor(self, tensor_index: int) -> np.ndarray:
        return self._tensor_data[tensor_index].copy()

    def invoke(self) -> None:
        for op_name, ins, outs, opts in self._ops:
            if op_name == "SHAPE":
                data = self._tensor_data[ins[0]]
                self._tensor_data[outs[0]] = np.array(data.shape, dtype=np.int32)
            elif op_name == "STRIDED_SLICE":
                self._exec_strided_slice(ins, outs[0], opts)
            elif op_name == "PACK":
                axis = opts.get("axis", 0)
                inputs = [self._tensor_data[i] for i in ins]
                self._tensor_data[outs[0]] = np.stack(inputs, axis=axis)
            elif op_name == "RESHAPE":
                if len(ins) > 1 and ins[1] >= 0 and self._tensor_data.get(ins[1]) is not None:
                    new_shape = list(self._tensor_data[ins[1]].flatten().astype(np.int32))
                else:
                    new_shape = self._tensor_meta[outs[0]]["shape"]
                self._tensor_data[outs[0]] = self._tensor_data[ins[0]].reshape(new_shape)
            elif op_name == "MEAN":
                self._exec_mean(ins, outs[0], opts)
            elif op_name == "CONV_2D":
                self._exec_conv2d(ins, outs[0], opts)
            elif op_name == "DEPTHWISE_CONV_2D":
                self._exec_depthwise_conv2d(ins, outs[0], opts)
            elif op_name == "AVERAGE_POOL_2D":
                self._exec_avgpool2d(ins[0], outs[0], opts)
            elif op_name == "FULLY_CONNECTED":
                self._exec_fully_connected(ins, outs[0], opts)
            elif op_name == "SOFTMAX":
                self._exec_softmax(ins[0], outs[0])
            else:
                raise RuntimeError(f"tflite_numpy_interpreter: unsupported op '{op_name}'")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _dequantize(self, idx: int) -> np.ndarray:
        info = self._tensor_meta[idx]
        t = self._tensor_data[idx]
        if info["dtype"] == np.int8:
            scale = info["scale"]
            zp = info["zero_point"]
            if isinstance(scale, np.ndarray):
                # Per-channel: broadcast along the quantized dimension
                ndim = t.ndim
                quant_dim = info.get("quantized_dimension", 0)
                bcast_shape = [1] * ndim
                bcast_shape[quant_dim] = len(scale)
                return (t.astype(np.float32) - zp.astype(np.float32).reshape(bcast_shape)) * scale.reshape(bcast_shape)
            return (t.astype(np.float32) - float(zp)) * float(scale)
        return t.astype(np.float32)

    def _requantize(self, x_f32: np.ndarray, out_idx: int) -> np.ndarray:
        info = self._tensor_meta[out_idx]
        if info["dtype"] == np.int8:
            sc = info["scale"]
            zp = info["zero_point"]
            sc = float(sc) if not isinstance(sc, np.ndarray) else float(sc.flat[0])
            zp = int(zp) if not isinstance(zp, np.ndarray) else int(zp.flat[0])
            return _quantize_i8(x_f32, sc, zp)
        return x_f32

    def _bias_float(self, bias_idx: int, inp_idx: int, wt_idx: int) -> np.ndarray:
        """Dequantize int32 bias to float32 using combined scale."""
        bias_i32 = self._tensor_data[bias_idx].astype(np.float32)
        inp_sc = self._tensor_meta[inp_idx]["scale"]
        wt_sc = self._tensor_meta[wt_idx]["scale"]
        inp_sc = float(inp_sc) if not isinstance(inp_sc, np.ndarray) else float(inp_sc.flat[0])
        if isinstance(wt_sc, np.ndarray):
            return bias_i32 * (inp_sc * wt_sc)  # [C_out]
        return bias_i32 * (inp_sc * float(wt_sc))

    def _parse_options(self, op, builtin_code: int) -> dict:
        opts: dict = {}
        if op.BuiltinOptionsType() == 0:
            return opts
        raw = op.BuiltinOptions()
        if raw is None:
            return opts

        if builtin_code == BuiltinOperator.CONV_2D:
            from tflite.Conv2DOptions import Conv2DOptions
            o = Conv2DOptions()
            o.Init(raw.Bytes, raw.Pos)
            opts = {"padding": o.Padding(), "stride_h": o.StrideH(), "stride_w": o.StrideW(),
                    "activation": o.FusedActivationFunction()}

        elif builtin_code == BuiltinOperator.DEPTHWISE_CONV_2D:
            from tflite.DepthwiseConv2DOptions import DepthwiseConv2DOptions
            o = DepthwiseConv2DOptions()
            o.Init(raw.Bytes, raw.Pos)
            opts = {"padding": o.Padding(), "stride_h": o.StrideH(), "stride_w": o.StrideW(),
                    "depth_multiplier": o.DepthMultiplier(), "activation": o.FusedActivationFunction()}

        elif builtin_code == BuiltinOperator.AVERAGE_POOL_2D:
            from tflite.Pool2DOptions import Pool2DOptions
            o = Pool2DOptions()
            o.Init(raw.Bytes, raw.Pos)
            opts = {"padding": o.Padding(), "stride_h": o.StrideH(), "stride_w": o.StrideW(),
                    "filter_h": o.FilterHeight(), "filter_w": o.FilterWidth(),
                    "activation": o.FusedActivationFunction()}

        elif builtin_code == BuiltinOperator.FULLY_CONNECTED:
            from tflite.FullyConnectedOptions import FullyConnectedOptions
            o = FullyConnectedOptions()
            o.Init(raw.Bytes, raw.Pos)
            opts = {"activation": o.FusedActivationFunction()}

        elif builtin_code == BuiltinOperator.SOFTMAX:
            from tflite.SoftmaxOptions import SoftmaxOptions
            o = SoftmaxOptions()
            o.Init(raw.Bytes, raw.Pos)
            opts = {"beta": o.Beta()}

        elif builtin_code == BuiltinOperator.STRIDED_SLICE:
            from tflite.StridedSliceOptions import StridedSliceOptions
            o = StridedSliceOptions()
            o.Init(raw.Bytes, raw.Pos)
            opts = {
                "begin_mask": o.BeginMask(), "end_mask": o.EndMask(),
                "ellipsis_mask": o.EllipsisMask(), "new_axis_mask": o.NewAxisMask(),
                "shrink_axis_mask": o.ShrinkAxisMask(),
            }

        elif builtin_code == BuiltinOperator.PACK:
            from tflite.PackOptions import PackOptions
            o = PackOptions()
            o.Init(raw.Bytes, raw.Pos)
            opts = {"values_count": o.ValuesCount(), "axis": o.Axis()}

        elif builtin_code == BuiltinOperator.MEAN:
            from tflite.ReducerOptions import ReducerOptions
            o = ReducerOptions()
            o.Init(raw.Bytes, raw.Pos)
            opts = {"keep_dims": o.KeepDims()}

        return opts

    # ------------------------------------------------------------------
    # Op implementations
    # ------------------------------------------------------------------

    def _exec_strided_slice(self, ins: list[int], out_idx: int, opts: dict) -> None:
        data = self._tensor_data[ins[0]]
        begin = list(self._tensor_data[ins[1]].flatten().astype(np.int32))
        end = list(self._tensor_data[ins[2]].flatten().astype(np.int32))
        strides = list(self._tensor_data[ins[3]].flatten().astype(np.int32))
        begin_mask = opts.get("begin_mask", 0)
        end_mask = opts.get("end_mask", 0)
        shrink_axis_mask = opts.get("shrink_axis_mask", 0)

        index_expr = []
        for dim in range(data.ndim):
            if (shrink_axis_mask >> dim) & 1:
                b = 0 if (begin_mask >> dim) & 1 else (begin[dim] if dim < len(begin) else 0)
                index_expr.append(int(b))
            else:
                b = 0 if (begin_mask >> dim) & 1 else (begin[dim] if dim < len(begin) else 0)
                e = data.shape[dim] if (end_mask >> dim) & 1 else (end[dim] if dim < len(end) else data.shape[dim])
                s = strides[dim] if dim < len(strides) else 1
                index_expr.append(slice(b, e, s))
        self._tensor_data[out_idx] = data[tuple(index_expr)]

    def _exec_mean(self, ins: list[int], out_idx: int, opts: dict) -> None:
        inp_f = self._dequantize(ins[0])
        axes = tuple(self._tensor_data[ins[1]].flatten().astype(np.int32).tolist())
        keep_dims = opts.get("keep_dims", False)
        result = np.mean(inp_f, axis=axes, keepdims=keep_dims).astype(np.float32)
        self._tensor_data[out_idx] = self._requantize(result, out_idx)

    def _exec_conv2d(self, ins: list[int], out_idx: int, opts: dict) -> None:
        inp_f = self._dequantize(ins[0])       # [B, H, W, C_in]
        wt_f = self._dequantize(ins[1])        # [C_out, kH, kW, C_in]
        bias_f = self._bias_float(ins[2], ins[0], ins[1])  # [C_out]

        B, in_h, in_w, _ = inp_f.shape
        C_out, kH, kW, _ = wt_f.shape
        sh, sw = opts["stride_h"], opts["stride_w"]

        if opts["padding"] == TFLPadding.SAME:
            pt, pb, pl, pr = _same_padding(in_h, in_w, kH, kW, sh, sw)
            inp_f = np.pad(inp_f, ((0, 0), (pt, pb), (pl, pr), (0, 0)))

        _, pH, pW, C_in = inp_f.shape
        out_h = (pH - kH) // sh + 1
        out_w = (pW - kW) // sw + 1

        # im2col: [B*out_h*out_w, kH*kW*C_in]
        shape = (B, out_h, out_w, kH, kW, C_in)
        strides = (
            inp_f.strides[0],
            inp_f.strides[1] * sh,
            inp_f.strides[2] * sw,
            inp_f.strides[1],
            inp_f.strides[2],
            inp_f.strides[3],
        )
        patches = np.lib.stride_tricks.as_strided(inp_f, shape=shape, strides=strides)
        col = patches.reshape(B * out_h * out_w, kH * kW * C_in)
        wt_col = wt_f.reshape(C_out, kH * kW * C_in)
        out_f = (col @ wt_col.T + bias_f).reshape(B, out_h, out_w, C_out)

        out_f = _clip_activation(out_f, opts["activation"])
        self._tensor_data[out_idx] = self._requantize(out_f, out_idx)

    def _exec_depthwise_conv2d(self, ins: list[int], out_idx: int, opts: dict) -> None:
        inp_f = self._dequantize(ins[0])       # [B, H, W, C]
        wt_f = self._dequantize(ins[1])        # [1, kH, kW, C*M]
        bias_f = self._bias_float(ins[2], ins[0], ins[1])  # [C*M]

        B, in_h, in_w, C = inp_f.shape
        _, kH, kW, CM = wt_f.shape
        M = CM // C  # depth_multiplier
        sh, sw = opts["stride_h"], opts["stride_w"]

        if opts["padding"] == TFLPadding.SAME:
            pt, pb, pl, pr = _same_padding(in_h, in_w, kH, kW, sh, sw)
            inp_f = np.pad(inp_f, ((0, 0), (pt, pb), (pl, pr), (0, 0)))

        _, pH, pW, _ = inp_f.shape
        out_h = (pH - kH) // sh + 1
        out_w = (pW - kW) // sw + 1

        # patches: [B, out_h, out_w, kH, kW, C]
        shape = (B, out_h, out_w, kH, kW, C)
        strides = (
            inp_f.strides[0],
            inp_f.strides[1] * sh,
            inp_f.strides[2] * sw,
            inp_f.strides[1],
            inp_f.strides[2],
            inp_f.strides[3],
        )
        patches = np.lib.stride_tricks.as_strided(inp_f, shape=shape, strides=strides)
        # [B, out_h, out_w, kH*kW, C]
        patches_flat = patches.reshape(B, out_h, out_w, kH * kW, C)
        # weight: [kH*kW, C, M]
        wt_reshaped = wt_f.reshape(kH * kW, C, M)
        # output: [B, out_h, out_w, C, M] → [B, out_h, out_w, C*M]
        out_f = np.einsum("bhwkc,kcm->bhwcm", patches_flat, wt_reshaped).reshape(B, out_h, out_w, C * M) + bias_f

        out_f = _clip_activation(out_f, opts["activation"])
        self._tensor_data[out_idx] = self._requantize(out_f, out_idx)

    def _exec_avgpool2d(self, inp_idx: int, out_idx: int, opts: dict) -> None:
        inp_f = self._dequantize(inp_idx)      # [B, H, W, C]
        B, in_h, in_w, C = inp_f.shape
        fh, fw = opts["filter_h"], opts["filter_w"]
        sh, sw = opts["stride_h"], opts["stride_w"]

        if opts["padding"] == TFLPadding.SAME:
            pt, pb, pl, pr = _same_padding(in_h, in_w, fh, fw, sh, sw)
            inp_f = np.pad(inp_f, ((0, 0), (pt, pb), (pl, pr), (0, 0)))

        _, pH, pW, _ = inp_f.shape
        out_h = (pH - fh) // sh + 1
        out_w = (pW - fw) // sw + 1

        shape = (B, out_h, out_w, fh, fw, C)
        strides = (
            inp_f.strides[0],
            inp_f.strides[1] * sh,
            inp_f.strides[2] * sw,
            inp_f.strides[1],
            inp_f.strides[2],
            inp_f.strides[3],
        )
        patches = np.lib.stride_tricks.as_strided(inp_f, shape=shape, strides=strides)
        out_f = patches.mean(axis=(3, 4))  # [B, out_h, out_w, C]

        out_f = _clip_activation(out_f, opts.get("activation", 0))
        self._tensor_data[out_idx] = self._requantize(out_f, out_idx)

    def _exec_fully_connected(self, ins: list[int], out_idx: int, opts: dict) -> None:
        inp_f = self._dequantize(ins[0])       # [B, N]
        wt_f = self._dequantize(ins[1])        # [M, N]
        bias_f = self._bias_float(ins[2], ins[0], ins[1])  # [M]

        out_f = inp_f @ wt_f.T + bias_f       # [B, M]
        out_f = _clip_activation(out_f, opts["activation"])
        self._tensor_data[out_idx] = self._requantize(out_f, out_idx)

    def _exec_softmax(self, inp_idx: int, out_idx: int) -> None:
        inp_f = self._dequantize(inp_idx)
        shifted = inp_f - np.max(inp_f, axis=-1, keepdims=True)
        exp_vals = np.exp(shifted)
        out_f = exp_vals / np.sum(exp_vals, axis=-1, keepdims=True)
        self._tensor_data[out_idx] = self._requantize(out_f, out_idx)
