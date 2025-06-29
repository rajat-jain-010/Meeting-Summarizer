from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import whisper
import os
import tempfile
import magic
from langchain_community.llms import Ollama
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from transformers import pipeline
import re

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

whisper_model = whisper.load_model("small")
# llm = Ollama(model="tinyllama")
llm = Ollama(model='deepseek-r1:1.5b')
# llm = Ollama(model="qwen3:1.7b")

class TranscriptRequest(BaseModel):
    transcript: str

@app.post("/upload_audio_video/")
async def upload_audio_video(file: UploadFile = File(...)):
    """
    Handles uploading and processing of audio and video files.  It saves the uploaded
    file to a temporary location, checks the file type, and then uses whisper to
    transcribe the audio.  The temporary file is then deleted.

    Args:
        file (UploadFile): The file to upload.

    Returns:
        dict: A dictionary containing the transcript of the audio.

    Raises:
        HTTPException: If the file type is not supported or if there is an error
                       during processing.
    """
    try:
        # Create a temporary file.
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_content = await file.read()
            tmp.write(file_content)
            tmp_path = tmp.name 

        # Determine the file type using libmagic.
        mime_type = magic.from_file(tmp_path, mime=True)

        # Check if the file is an audio or video file that whisper can process
        if not mime_type.startswith("audio/") and not mime_type.startswith("video/"):
            os.remove(tmp_path)
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type.  Must be audio or video.  Got {mime_type}",
            )

        result = whisper_model.transcribe(tmp_path)

        os.remove(tmp_path)
        return {"transcript": result["text"]}
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(
            status_code=500, detail=f"Error processing file: {e}"
        )

summary_prompt_template = """
You are a helpful assistent that can help make a summary of the text.
Please generate a concise summary of the from the transcript below. Focus on the main discussion points, decisions made, and important highlights.

===Transcript:
{text}

===Response guideline:
- You should write summary based only on the provided information.
- Keep the summary factual and to the point.
- Avoid adding interpretations or assumptions.
- Donot give the heading summary.
"""

keypoints_prompt_template = """
You are a helpful assistent that can help take note of key points of the provided text.
Please extract and list the key discussion points from the transcript below.

===Transcript:
{text}

===Response guideline:
- You should give keypoints based only on the provided information.
- Present the output as bullet points.
- Focus only on the core discussion points; do not include filler or small talk.
- Avoid full sentences where possible—keep it concise.
- Donot give more than 10 points.
"""

action_items_prompt_template = """
From the following transcript, extract all action items discussed or agreed upon. Each item should be specific, actionable, and ideally include who is responsible (if known).

Transcript:
{text}

Answer format:
1. Task: ...
   Assigned to: ...
   Deadline (if any): ...
2. Task: ...
   Assigned to: ...
   Deadline: ...
"""

problem_solution_tech_prompt_template="""
Analyze the transcript below and extract all
1. Problem statements mentioned in the discussion. List them clearly and concisely.
2. Propose Solutions for each problem statement.
3. Recommended technology stack for each solution.

===Transcript:
{text}

===Response Guidelines:
1. Problem: ...
   Solution: ...
   Technology Stack Recommendation: ...
2. Problem: ...
   Solution: ...
   Technology Stack Recommendation: ...
"""


PROBLEM_SOLUTION_TECH_PROMPT = PromptTemplate(template=problem_solution_tech_prompt_template ,input_variables=["text"])
SUMMARY_PROMPT = PromptTemplate(template=summary_prompt_template, input_variables=["text"])
KEYPOINT_PROMPT = PromptTemplate(template=keypoints_prompt_template, input_variables=["text"])
ACTION_ITEM_PROMPT = PromptTemplate(template=action_items_prompt_template, input_variables=["text"])


# Load BERT model for classification
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
candidate_labels = [
    "Technical Meeting",
    "Non-Technical Meeting"
]

def clean_thought_blocks(generated_text: str) -> str:
    """
    Removes everything enclosed within <think> and </think> tags from a string.

    Args:
        generated_text: The input string that may contain <think> blocks.

    Returns:
        The string with all <think> blocks and their content removed.
    """
    cleaned_text = re.sub(r"<think>.*?</think>", "", generated_text, flags=re.DOTALL).strip()
    return cleaned_text

@app.post("/generate_report/")
async def generate_report(req: TranscriptRequest):
    """
    Generates a report from a meeting transcript using LangChain and a locally
    deployed TinyLlama model.

    Args:
        req (TranscriptRequest): The request containing the meeting transcript.

    Returns:
        dict: A dictionary containing the generated report.
    """
    try:
        text = req.transcript

        discussion_type_output = classifier(text, candidate_labels)
        discussion_type = discussion_type_output['labels'][0]


        # Define chains
        summary_chain = LLMChain(llm=llm, prompt=SUMMARY_PROMPT)
        keypoint_chain = LLMChain(llm=llm, prompt=KEYPOINT_PROMPT)

        summary_output = clean_thought_blocks(summary_chain.run(text))
        keypoint_output = clean_thought_blocks(keypoint_chain.run(text))


        if discussion_type == 'Technical Meeting':
            problem_solution_tech_chain = LLMChain(llm=llm, prompt=PROBLEM_SOLUTION_TECH_PROMPT)
            action_item_chain = LLMChain(llm=llm, prompt=ACTION_ITEM_PROMPT)

            problem_solution_tech_output = clean_thought_blocks(problem_solution_tech_chain.run(text))
            action_item_output = clean_thought_blocks(action_item_chain.run(text))


            response = {
                "discussion_type": discussion_type,
                "summary": summary_output,
                "keypoint": keypoint_output,
                "problem_solution_tech": problem_solution_tech_output,
                "action_item": action_item_output,
            }

        else:
            response = {
                "discussion_type": discussion_type,
                "summary": summary_output,
                "keypoint": keypoint_output,
                "problem_solution_tech": None,
                "action_item": None,
            }

        # print("---------------------------------------------------------------")
        # print('backend report: ')
        # print(response)
        # print("---------------------------------------------------------------")

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating report: {e}"
        )