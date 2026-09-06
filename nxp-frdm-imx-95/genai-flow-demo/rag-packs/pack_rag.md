Retrieval-Augmented Generation, or RAG, is a technique that gives a language model access to an external knowledge base at query time. Instead of relying only on what the model memorized during training, RAG retrieves relevant passages and adds them to the prompt so the model can answer from real source text.

RAG solves two problems with language models: hallucination, where a model invents plausible but false facts, and staleness, where a model does not know information created after its training. Retrieving current, authoritative passages grounds the answer in real documents.

A RAG database is built by taking source documents, splitting them into small pieces called chunks, converting each chunk into a numerical vector with an embedding model, and storing those vectors so they can be searched by similarity.

Chunking is the process of splitting documents into retrieval-sized pieces. Good chunks are self-contained and focused on a single idea, usually a paragraph or a few sentences, so that a retrieved chunk makes sense on its own without surrounding context.

An embedding is a list of numbers, a vector, that represents the meaning of a piece of text. Texts with similar meanings have vectors that are close together, which lets the system find passages related to a question even when they use different words.

An embedding model is a neural network that turns text into embeddings. Small, fast embedding models such as MiniLM produce a few hundred dimensions and run easily on edge devices; larger models capture more nuance at higher cost.

A vector database, or vector store, holds the embeddings and supports similarity search: given a query vector, it quickly returns the stored chunks whose vectors are nearest. Examples include FAISS, Chroma, Milvus, and pgvector.

At query time, the user's question is embedded with the same embedding model used for the documents, and the vector store returns the top-k most similar chunks. Those chunks are inserted into the prompt as context for the language model.

Similarity between vectors is usually measured with cosine similarity, which compares the angle between two vectors, or with Euclidean distance. Higher cosine similarity means the texts are more semantically related.

The parameter k, the number of chunks retrieved, is a key tuning knob. Too few chunks may miss the answer; too many add noise and can push relevant text out of the model's limited context window.

A reranker is an optional second stage that re-scores the retrieved chunks with a more accurate model, promoting the truly relevant passages above merely similar ones before they are sent to the language model.

Retrieval quality depends heavily on phrasing and keywords. A question dominated by a common term can retrieve the wrong chunk, so distinctive wording and well-written, single-topic chunks improve the odds of grounding on the right passage.

The context window is the maximum amount of text a language model can consider at once. RAG must fit the retrieved chunks plus the question and the answer within this limit, which is why chunks are kept small and only the top matches are used.

RAG keeps data private and local when it runs on-device: the documents and the embedding search stay on the hardware, and only the final prompt is processed by the local model, so sensitive information never leaves the device.

Updating a RAG system is cheap compared with retraining a model. To add new knowledge you simply chunk and embed the new documents and add them to the vector store; the language model itself does not need to change.

A good RAG answer quotes or closely follows the retrieved source, so it can be checked against the original documents. Some systems return citations pointing to the exact passages used, making the answer auditable.

RAG is different from fine-tuning. Fine-tuning changes the model's weights to bake in new behavior or knowledge, while RAG leaves the model unchanged and supplies knowledge at query time. The two techniques can be combined.

When a question is outside the knowledge base, a well-built RAG system should recognize that no relevant chunk was retrieved and decline to answer rather than inventing a response. Refusing to answer off-topic questions is a feature, not a failure.

Preprocessing documents for RAG often includes cleaning text, removing boilerplate, and normalizing formatting, because clean, well-structured source text produces better chunks and better retrieval.

On an edge device like the NXP i.MX 95, a RAG pipeline combines a small embedding model, an on-device vector store, and a small language model, letting the board answer questions grounded in a local knowledge base entirely offline.
