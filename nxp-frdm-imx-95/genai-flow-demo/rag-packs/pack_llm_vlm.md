A large language model, or LLM, is a neural network trained on vast amounts of text to predict the next piece of text. By repeatedly predicting the most likely next token, it can generate fluent answers, summaries, code, and conversation.

A token is the basic unit a language model reads and writes. A token is roughly four characters or about three-quarters of a word in English. Models process text as sequences of tokens, not raw characters.

The weights, or parameters, of a model are the numbers it learned during training. Model size is measured in parameters: a 500-million-parameter model is small, while frontier models have hundreds of billions. More parameters generally mean more capability but also more memory and compute.

Generation speed is usually measured in tokens per second. Because producing each token requires reading essentially all of the model's weights once, generation speed is limited by memory bandwidth, not just raw compute.

Time to first token, or TTFT, is how long the model takes to produce its first token after receiving a prompt. It is separate from generation speed; a model can start quickly yet still take time to type a long answer.

The Transformer is the neural network architecture behind almost all modern language models. Its key innovation is the attention mechanism, which lets the model weigh the relevance of every token to every other token when producing output.

Attention is the mechanism that lets a model focus on the most relevant parts of the input when generating each token. It is what allows models to track context across a long passage.

The context window is the maximum number of tokens a model can consider at once, including the prompt and the generated answer. Larger context windows let a model read more input but cost more memory and time.

Training an LLM has two main phases: pretraining on huge text corpora to learn language, and fine-tuning or alignment on curated examples to make it follow instructions and behave helpfully and safely.

Quantization shrinks a model by storing its weights at lower numerical precision, for example 8-bit or 4-bit integers instead of 16-bit floating point. This reduces memory and speeds up generation, usually with a small loss in answer quality.

Small language models, with hundreds of millions to a few billion parameters, can run on edge devices like the NXP i.MX 95. They are fast and private but more prone to factual errors, which is why techniques like RAG and agents are used to ground them.

Hallucination is when a language model produces fluent, confident text that is factually wrong. It happens because the model predicts plausible text rather than looking up facts. Smaller models hallucinate more, especially on niche or recent topics.

A vision-language model, or VLM, is a model that understands both images and text. It can answer questions about a picture, describe a scene, read text in an image, or compare visual details, combining sight with language.

A VLM is built from two parts: a vision encoder that turns an image into a set of numerical features, and a language model decoder that reasons over those features together with the text prompt to produce an answer.

The vision encoder processes the image once per question, converting it into tokens the language model can attend to. This encode step is a fixed cost per image, separate from the per-token cost of generating the text answer.

SmolVLM is a family of small vision-language models designed to run on modest hardware. On the demo board, SmolVLM answers questions about a live camera frame entirely on-device, so the image never leaves the board.

For best results, a VLM should be asked open or scene-appropriate questions such as describe what you see. Leading questions about things that are not in the image can prompt the model to invent details that are not there.

Multimodal means a model works with more than one kind of data, such as text and images together. VLMs are multimodal; some newer models also handle audio and video.

Inference is the act of running a trained model to produce output, as opposed to training, which creates the model. Edge AI focuses on doing inference locally on the device rather than sending data to the cloud.

Running models on the edge, on hardware like the i.MX 95 with its Neutron NPU or an attached Ara240 accelerator, keeps data private, works without a network, and gives predictable low latency, at the cost of running smaller models than the cloud can.
