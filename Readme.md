# AI-Researcher

AI-Researcher is a multi-agent system designed to automate the process of conducting research, generating reports, and publishing them in various formats. It leverages AI agents to perform tasks such as researching, writing, reviewing, revising, and publishing, with support for human feedback and customizable guidelines.

## Project Overview

AI-Researcher is structured as a full-stack application with a frontend for user interaction and a backend for processing research tasks. The system uses a multi-agent architecture where specialized agents collaborate to produce high-quality research reports. The project includes a WebSocket-based logging system for real-time updates and a vector store for efficient information retrieval.

## Flow of the Application

The workflow of AI-Researcher is orchestrated by a `ChiefEditorAgent` that coordinates the following agents:

1. **ResearchAgent**: Conducts initial and in-depth research using the `gpt-researcher` library, querying external sources or reusing existing data from a global vector store.
2. **EditorAgent**: Plans the research outline, defining sections based on the initial research and user-specified parameters.
3. **HumanAgent**: Optionally collects human feedback on the research plan, allowing users to refine the outline.
4. **WriterAgent**: Generates the introduction, conclusion, table of contents, and references, ensuring compliance with guidelines (e.g., APA format).
5. **ReviewerAgent**: Reviews drafts against guidelines, providing feedback or accepting the draft for publication.
6. **ReviserAgent**: Revises drafts based on reviewer feedback, maintaining the original structure where possible.
7. **PublisherAgent**: Publishes the final report in user-specified formats (Markdown, PDF, DOCX).

The process starts with a user query submitted via the frontend, which triggers the backend to initiate a research task. The agents work in a defined sequence, with conditional logic for human feedback and revisions, culminating in a published report stored in the `outputs` directory.

## Frontend

The frontend is built using:

- **Flask**: A lightweight Python web framework for serving the web interface.
- **HTML/CSS/JavaScript**: The user interface is defined in `frontend/templates/index.html`, styled with **Tailwind CSS** (via CDN) and enhanced with custom CSS for dark mode and log styling.
- **WebSocket**: Used for real-time communication with the backend to display logs and handle chat queries.
- **Features**:
  - A form to input research queries and configure settings (tone, max sections, output formats, model, guidelines, etc.).
  - A real-time log display with agent-specific styling and emojis.
  - A download section for retrieving generated reports in various formats.
  - A chat interface to query the generated report using the vector store.

The frontend communicates with the backend via HTTP POST requests to `/start_research` and WebSocket connections to `/ws/{task_id}`.

## Backend

The backend is built using:

- **FastAPI**: A modern Python web framework for building APIs, handling WebSocket connections, and serving static files (reports in the `outputs` directory).
- **Python**: The core language for implementing the multi-agent system and supporting utilities.
- **LangGraph**: Used to define and manage the workflow of agents, enabling stateful and conditional transitions.
- **WebSocket**: Facilitates real-time logging and chat functionality.
- **FAISS**: A library for efficient similarity search, used to create and query vector indices for report chunks.
- **Features**:
  - Endpoints for starting research (`/start_research`), retrieving logs (`/logs`), checking task status (`/task_status/{task_id}`), and WebSocket communication (`/ws/{task_id}`).
  - A multi-agent system with modular agent classes (`ResearchAgent`, `EditorAgent`, etc.) in `multi_agents/agents`.
  - Vector indexing for efficient retrieval of report chunks, stored in `outputs/{task_id}/faiss_index` and a global vector store.
  - Support for multiple output formats (Markdown, PDF, DOCX) via utilities in `multi_agents/agents/utils/file_formats.py`.

## Flow Diagram

The flow diagram illustrating the agent interactions and workflow is located at `./src/flow_diagram.png`. It visually represents the sequence of tasks, from query submission to report publication, including conditional paths for human feedback and revisions.

## Setup Instructions

To set up AI-Researcher locally, follow these steps:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Kaustubh-Rathi/Shyftlabs.git
   cd AI-Researcher
   ```

2. **Create a Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   Install the required libraries listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**:
   Create a `.env` file in the root directory and add the following API keys:
   ```
   OPENAI_API_KEY=<your_openai_api_key>
   TAVILY_API_KEY=<your_tavily_api_key>
   LANGCHAIN_API_KEY=<your_langchain_api_key>
   HF_TOKEN=<your_huggingface_token>
   ```
   - Obtain `OPENAI_API_KEY` from [OpenAI](https://platform.openai.com/).
   - Obtain `TAVILY_API_KEY` from [Tavily](https://tavily.com/).
   - Obtain `LANGCHAIN_API_KEY` from [LangChain](https://www.langchain.com/).
   - Obtain `HF_TOKEN` from [Hugging Face](https://huggingface.co/).

5. **Run the Backend**:
   Start the FastAPI server:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

6. **Run the Frontend**:
   In a separate terminal, start the Flask server:
   ```bash
   python frontend/app.py
   ```

7. **Access the Application**:
   Open a browser and navigate to `http://localhost:8080` to access the web interface.

8. **Optional: View Logs**:
   Logs are displayed in the frontend UI and also stored in memory for retrieval via the `/logs` endpoint.

## Important Libraries

The project relies on the following key libraries:

- **FastAPI**: For building the backend API and WebSocket server.
- **Flask**: For serving the frontend web interface.
- **LangGraph**: For orchestrating the multi-agent workflow.
- **gpt-researcher**: For conducting research and generating content.
- **FAISS**: For vector indexing and similarity search.
- **Pydantic**: For data validation and modeling (e.g., `ResearchRequest`).
- **Uvicorn**: ASGI server for running FastAPI.
- **Colorama**: For colored terminal output.
- **JSON5**: For parsing JSON with relaxed syntax.
- **Tailwind CSS**: For frontend styling (via CDN).
- **WebSocket**: For real-time communication between frontend and backend.
- **Python-Dotenv**: For loading environment variables from a `.env` file.

Additional dependencies are listed in `requirements.txt`.

## Notes

- Ensure the `outputs` directory is writable, as it stores generated reports and vector indices.
- The global vector store (`Example_outputs/global_vector_store`) enables reuse of research data across tasks.
- The application supports multiple AI models (e.g., GPT-3.5 Turbo, GPT-4), configurable via the frontend.
- For production use, consider securing the WebSocket and API endpoints and optimizing the vector store for scalability.
