# 🎬 NeuralMeet: AI Video Intelligence

![NeuralMeet Banner](https://img.shields.io/badge/NeuralMeet-AI_Video_Assistant-8b5cf6?style=for-the-badge&logo=openai&logoColor=white)

NeuralMeet is an end-to-end AI pipeline that transforms YouTube videos and local media files into actionable meeting intelligence. Built with a stunning, production-ready Streamlit UI, it automatically transcribes audio, generates executive summaries, extracts key action items, and allows you to chat with your media using a Retrieval-Augmented Generation (RAG) engine.

## ✨ Features

- **🎙️ State-of-the-art Transcription:** Uses OpenAI's Whisper model (runs locally) for high-accuracy speech-to-text. Supports English and Hinglish (via Sarvam AI).
- **📋 Smart Summarization:** Leverages LangChain and Mistral LLM to distill hours of content into structured executive briefs and auto-generate session titles.
- **✅ Action Extraction:** Automatically pulls out action items, key decisions, and open questions from the transcript.
- **🧠 RAG Chat Engine:** Chat directly with your meeting! Uses ChromaDB vector store and HuggingFace embeddings to retrieve exact context and answer any questions about the session.
- **📤 Export to PDF/TXT:** Instantly download a beautifully branded PDF report or raw text files.
- **🗂️ Session History:** All analyzed sessions are saved locally, fully searchable, and can be reopened at any time.
- **💎 Premium UI/UX:** A jaw-dropping glassmorphism design with animated aurora backgrounds, neon glows, and interactive micro-animations.

## 🛠️ Tech Stack

- **Frontend:** Streamlit, Custom CSS (Glassmorphism, Animations)
- **Audio Processing:** `yt-dlp`, `pydub`, `FFmpeg`
- **AI / ML Models:**
  - **Transcription:** OpenAI Whisper (Local CPU/GPU) / Sarvam AI
  - **LLM Orchestration:** LangChain
  - **LLM Provider:** Mistral AI (`langchain-mistralai`)
  - **Embeddings:** HuggingFace (`all-MiniLM-L6-v2`)
  - **Vector Database:** ChromaDB

## 🚀 Getting Started (Local Setup)

### Prerequisites
- Python 3.9+
- [FFmpeg](https://ffmpeg.org/) installed and added to your system PATH (or installed via `winget`).

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/vikassourc/neuralmeet.git
   cd neuralmeet
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Mac/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory and add your API keys:
   ```env
   MISTRAL_API_KEY=your_mistral_api_key_here
   SARVAM_API_KEY=your_sarvam_api_key_here  # Only needed for Hinglish translation
   WHISPER_MODEL=small  # Options: tiny, base, small, medium, large
   ```

### Running the App

```bash
streamlit run app.py
```
The app will open automatically in your browser at `http://localhost:8501`.

## 📁 Project Structure

```text
neuralmeet/
├── app.py                  # Streamlit UI entry point
├── core/
│   ├── extractor.py        # Prompts for Action Items & Decisions
│   ├── rag_engine.py       # ChromaDB setup and QA chain
│   ├── summarizer.py       # Summarization and Title generation
│   ├── transcriber.py      # Whisper / Sarvam audio transcription
│   └── vector_store.py     # Embeddings management
├── utils/
│   └── audio_processor.py  # yt-dlp downloading and FFmpeg chunking
├── requirements.txt        # Python dependencies
└── packages.txt            # System dependencies for cloud deployment
```

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/vikassourc/neuralmeet/issues).

## 📄 License
This project is licensed under the MIT License.
