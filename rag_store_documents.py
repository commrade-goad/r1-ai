import os
import tempfile
from typing import List

from dotenv import load_dotenv
from fastapi import UploadFile
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from supabase import create_client, Client

# Muat environment variables dari file .env
load_dotenv()

# --- INISIALISASI KLIEN (dilakukan sekali saat modul dimuat) ---
try:
    # Kredensial Supabase
    SUPABASE_URL: str = os.environ["R_SUPABASE_URL"]
    SUPABASE_KEY: str = os.environ["R_SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Nama Bucket & Folder Supabase
    BUCKET_NAME: str = os.environ.get("SUPABASE_BUCKET", "dataset-khotbah")
    FOLDER_PATH: str = os.environ.get("SUPABASE_FOLDER", "khotbah")

    # Kredensial Pinecone
    PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
    INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "khotbah-summarizer-app")

    # Inisialisasi Klien Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)

    # Inisialisasi Model Embedding OpenAI
    embeddings_model = OpenAIEmbeddings(model='text-embedding-3-small')
    
    # Inisialisasi Pinecone Vector Store
    vectorstore = PineconeVectorStore(index_name=INDEX_NAME, embedding=embeddings_model)
    
    # Inisialisasi Text Splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=250,
        chunk_overlap=75,
        length_function=len,
        is_separator_regex=False,
    )
    print("Klien dan model berhasil diinisialisasi.")

except KeyError as e:
    print(f"Error: Environment variable tidak ditemukan -> {e}. Pastikan file .env sudah benar.")
    exit()
except Exception as e:
    print(f"Gagal menginisialisasi klien: {e}")
    exit()

# --- FUNGSI UTAMA UNTUK MEMPROSES FILE ---
async def process_and_add_documents(files: List[UploadFile]) -> dict:
    """
    Menerima file PDF, mengunggahnya ke Supabase, memprosesnya, 
    dan menambahkan vektornya ke Pinecone.
    """
    all_new_documents = []
    processed_files_info = []

    # Buat direktori sementara yang unik untuk pemrosesan ini
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in files:
            if not file.filename:
                print("Peringatan: Ditemukan file unggahan tanpa nama, file ini dilewati.")
                continue 

            file_path_in_bucket = f"{FOLDER_PATH}/{file.filename}"
            temp_file_path = os.path.join(temp_dir, file.filename)

            try:
                # 1. Simpan file yang diunggah ke disk sementara
                content = await file.read()
                with open(temp_file_path, "wb") as f:
                    f.write(content)

                # 2. Upload file ke Supabase Storage
                # 'upsert=True' akan menimpa file jika namanya sudah ada
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=file_path_in_bucket,
                    file=temp_file_path,
                    file_options={"cache-control": "3600", "upsert": "true", "content-type": "application/pdf"}
                )

                # 3. Dapatkan URL publik dari Supabase
                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path_in_bucket)
                print(f"Berhasil upload & mendapatkan URL: {public_url}")

                # 4. Load konten PDF menggunakan PyPDFLoader
                loader = PyPDFLoader(temp_file_path)
                documents_per_file = loader.load()

                # 5. Perbarui metadata 'source' dengan URL Supabase
                for doc in documents_per_file:
                    doc.metadata['source'] = public_url
                
                all_new_documents.extend(documents_per_file)
                processed_files_info.append({"filename": file.filename, "url": public_url})

            except Exception as e:
                print(f"GAGAL memproses file {file.filename}: {e}")
                # Jika gagal, lanjutkan ke file berikutnya
                continue
    
    if not all_new_documents:
        return {"status": "error", "message": "Tidak ada dokumen yang berhasil diproses."}

    try:
        # 6. Pecah dokumen menjadi chunk
        print(f"Memecah {len(all_new_documents)} halaman menjadi chunk...")
        all_chunks = text_splitter.split_documents(all_new_documents)
        print(f"Dibuat {len(all_chunks)} chunk baru.")

        # 7. Tambahkan chunk ke Pinecone (sudah termasuk proses embedding)
        print("Menambahkan chunk ke Pinecone...")
        vectorstore.add_documents(all_chunks, batch_size=100)
        
        return {
            "status": "success",
            "message": "Knowledge base berhasil diperbarui.",
            "files_processed": len(processed_files_info),
            "chunks_added": len(all_chunks),
            "details": processed_files_info
        }

    except Exception as e:
        print(f"GAGAL saat chunking atau upload ke Pinecone: {e}")
        return {"status": "error", "message": f"Gagal pada tahap akhir: {e}"}