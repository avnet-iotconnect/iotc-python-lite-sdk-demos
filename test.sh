#!/bin/bash
  rm -f ~/kvs-libs/*
  mkdir -p ~/kvs-libs
  sudo docker run --rm \
    -v ~/kvs-libs:/output \
    debian:bookworm bash -c '
      set -e
      dpkg --add-architecture arm64
      apt-get update -q && apt-get install -y -q \
        cmake git make pkg-config \
        clang lld crossbuild-essential-arm64
      apt-get install -y -q \
        libssl-dev:arm64 libcurl4-openssl-dev:arm64 \
        libgstreamer1.0-dev:arm64 libgstreamer-plugins-base1.0-dev:arm64 \
        liblog4cplus-dev:arm64
      echo "#!/bin/sh" > /usr/local/bin/arm64-pkg-config
      echo "exec env PKG_CONFIG_PATH=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig pkg-config \"\$@\"" >>
  /usr/local/bin/arm64-pkg-config
      chmod +x /usr/local/bin/arm64-pkg-config
      git clone https://github.com/awslabs/amazon-kinesis-video-streams-producer-sdk-cpp.git /kvs
      cd /kvs && mkdir build && cd build
      cmake .. \
        -DBUILD_GSTREAMER_PLUGIN=ON -DBUILD_JNI=OFF -DBUILD_DEPENDENCIES=OFF \
        -DCMAKE_C_COMPILER=clang \
        -DCMAKE_CXX_COMPILER=clang++ \
        -DCMAKE_C_FLAGS="--target=aarch64-linux-gnu" \
        -DCMAKE_CXX_FLAGS="--target=aarch64-linux-gnu" \
        -DCMAKE_EXE_LINKER_FLAGS="-fuse-ld=lld --target=aarch64-linux-gnu" \
        -DCMAKE_SHARED_LINKER_FLAGS="-fuse-ld=lld --target=aarch64-linux-gnu" \
        -DCMAKE_MODULE_LINKER_FLAGS="-fuse-ld=lld --target=aarch64-linux-gnu" \
        -DCMAKE_SYSTEM_NAME=Linux \
        -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
        -DCMAKE_LIBRARY_ARCHITECTURE=aarch64-linux-gnu \
        -DPKG_CONFIG_EXECUTABLE=/usr/local/bin/arm64-pkg-config \
        -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY
      make -j4
      find /kvs/build -name "*.so*" -type f -exec cp {} /output/ \;
      cp /usr/lib/aarch64-linux-gnu/liblog4cplus*.so* /output/ 2>/dev/null || true
      echo "Done. Files:" && ls /output/
    '
