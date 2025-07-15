## TEST FILE FOR RAG SERMON SUMMARIZER

from rag_sermon_summarizer import summarize_sermon


if __name__ == "__main__":
    user_input = "Apa yang diajarkan tentang semangat belajar?"

    summary = summarize_sermon(user_input)

    print("Ringkasan Khotbah:")
    print(summary.summary)
    print(summary.source_documents)
