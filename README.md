# Meeting-Summarizer


This project utilizes the power of LLMs to summarize the meeting transcripts directly or transforms audio/video file using whsiper to summarize, question, classify the discussion.


to run this project 

first run the model locally using ollama in background 

1. Backend 

    uvicorn main:app --reload

2. Frontend

    streamlit run app.py
