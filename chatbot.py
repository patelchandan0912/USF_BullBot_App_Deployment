import streamlit as st
import os
import pinecone
from langchain.chains import ConversationChain
from langchain.memory import ConversationSummaryMemory
from langchain.callbacks import get_openai_callback
from langchain.vectorstores import Pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from dataclasses import dataclass
from typing import Literal
from dotenv import load_dotenv, find_dotenv
from PIL import Image
import time
import PyPDF2
import openai
_ = load_dotenv(find_dotenv())

openai.api_key  = os.environ['OPENAI_API_KEY']
PINECONE_INDEX_NAME = "ms-bais-ta-project-index"

def load_css():
    """load the css to allow for styles.css to affect look and feel of the streamlit interface"""
    with open('static/styles.css', "r") as f:
         css = f"<style>{f.read()}</style>"
         st.markdown(css, unsafe_allow_html=True)
    

def initialize_vector_store():
    """Initialize a Pinecone vector store for similarity search."""
    
    pinecone.init(api_key=os.getenv('PINECONE_API_KEY'),environment=os.getenv('PINECONE_ENVIRONMENT') )
    index = pinecone.Index(PINECONE_INDEX_NAME) # you need to have pinecone index name already created (ingest.py should be run first)
    embed_model = OpenAIEmbeddings(model="text-embedding-ada-002")
    vectorstore = Pinecone(index, embed_model, "text") # 'text' is the field name in pinecone index where original text is stored
                           
    return vectorstore

def initialize_session_state():
    """Initialize the session state variables for streamlit."""
    
    if "history" not in st.session_state:
        st.session_state.history = []
    if "token_count" not in st.session_state:
        st.session_state.token_count = 0
    if "conversation" not in st.session_state:
        # create a connection to OpenAI text-generation API
        llm = ChatOpenAI(
            temperature=0.3,
            openai_api_key=os.environ["OPENAI_API_KEY"],
#            max_tokens=500,
#            model_name="gpt-3.5-turbo",
            model_name="gpt-4",
        )
        st.session_state.conversation = ConversationChain(
            llm=llm,
            memory=ConversationSummaryMemory(llm=llm),
            verbose=True,         
        )


@dataclass
class Message:
    """Class for keeping track of a chat message."""
    origin: Literal['human', 'ai']
    message: str
    
# when submit button is clicked, this function is called    
def on_click_callback(debug=True): #called on click of submit button
    """Function to handle the submit button click event."""
    # Add the spinner here
    # Add the spinner here
    with st.spinner("BullBot is thinking..."):
        
        with get_openai_callback() as cb:
                
            # get the human prompt in session state (read from text field)
            human_prompt = st.session_state.human_prompt
                
            # conduct a similarity search on our vector database
            vectorstore = initialize_vector_store()
            similar_docs = vectorstore.similarity_search(
                human_prompt,  # our search query
                k=25  # return relevant docs
            )
            
            # Check input to see if it flags the Moderation API or is a prompt injection
            mod_response = openai.Moderation.create(input=human_prompt)
            moderation_output = mod_response["results"][0]
            
            if moderation_output["flagged"]:
                if debug:
                    print("Input flagged by Moderation API.")
                prompt = f"""You are a moderation Check specialist. So, display this Message only "Please submit an alternative \\
                    query as the initial message was flagged by our system for potential abuse or unauthorized instructions." \\
                        Don't add AI text into the above message just give the above message as it is."""
            else:
                if debug:
                    print("Step 1: Input passed moderation check.")
                prompt = f"""
                Welcome to the USF Connect chatbot! 🐂 \\
                You are a friendly USF Bull chatbot, here to assist with any questions about the university or student life. \n
                Query:\n
                "{human_prompt}" \n\n                        
                    
                Context:" \n
                "{' '.join([doc.page_content for doc in similar_docs])}" \n
                    
                Note: If you don't know the answer to a question, politely acknowledge that you're unable to provide an answer at \\
                this time. Always maintain a helpful and courteous tone, and thank the user for their inquiry.\\
                """
            print(prompt) # for debugging purposes
    
            # get the llm response from prompt
            llm_response = st.session_state.conversation.run(
                prompt
            )
                
            #store the human prompt and llm response in the history buffer
            st.session_state.history.append(
                Message("human", human_prompt)
            )
            st.session_state.history.append(
                Message("ai", llm_response) 
            )
                
            # keep track of the number of tokens used
            st.session_state.token_count += cb.total_tokens



#############################
# MAIN PROGRAM

# initializations
load_dotenv() # load environment variables from .env file
load_css() # need to load the css to allow for styles.css to affect look and feel
initialize_session_state() # initialize the history buffer that is stored in UI  

# Load the USF Logo
image1 = Image.open('static/usf_pic1.jpg')
# Display the USF-Muma Logo
st.image(image1, use_column_width=True)

# Define a dictionary to store uploaded PDFs and their associated subjects
pdf_subjects = {}

# Define a function to extract text from a PDF file
def extract_text_from_pdf(uploaded_file):
    text = ""
    pdf = PyPDF2.PdfReader(uploaded_file)
    for page in pdf.pages:
        text += page.extract_text()
    return text

# Set Streamlit app title and header
st.title("USFConnect App: Your MS-BAIS Guide 🐂")
st.header("Welcome to USFConnect: Check for any Pre-requisite courses")

# Create a dropdown list of subjects
subject = st.selectbox("Select a Subject for which you want to check", ["Object-Oriented Programming(C# or Java)", "Systems Analysis & Design", "Database Management", "Financial Accounting", "Economics","Statistics",""])

# Create a file upload component
uploaded_file = st.file_uploader("Upload your bachelors course syllabus or equivalent experience certificate for the selected subject in PDF format (limit 200MB)", type=["pdf"])

# Check if a file has been uploaded
if uploaded_file is not None:
    # Extract text from the uploaded PDF
    extracted_text = extract_text_from_pdf(uploaded_file)
    
    # Create a prompt using the subject name
    prompt = f"""You are an academic director of USF MS in Business Analytics and Information Systems Program and your job is to \\
        decide whether a student has any pre-requisite course for MS BAIS Program at USF. \n\n \\
        Given the syllabus of a bachelor's degree program for a given subject, predict whether the given subject \\
        candidate requires that subject as a pre-requisite course in the MS BAIS Program at USF.\n\n \\
        Course: {subject} \n\n \\
        Syllabus: {extracted_text} \n\n \\
        Result: Prediction of whether or not the given subject candidate requires that subject as a pre-requisite \\
        course in the MS BAIS Program. If the candidate syllabus has the content of the subject or relevant part of the subject \\
        you can say that candidate meet the requirement and doesn't need this subject as Pre-requisite course in the program. \n\n \\
        Example \n\n \\
        Result: Based on the syllabus provided Object Oriented Programming is not a Pre-requisite course for you.\n 
        Note: If you don't know the answer to a question, politely acknowledge that you're unable to provide an answer at \\
        this time. Always maintain a helpful and courteous tone, and thank the user for their inquiry.\\
        """

# Create a button to check Pre-requisite
if st.button("Submit to CheckPre-requisite"):
    # Process the user's question and get a response from the GenAI Assistant
    # Add your code for question answering here
    def get_completion(prompt, model="gpt-4"):
        messages = [{"role": "user", "content": prompt}]
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=0.3, # this is the degree of randomness of the model's output
        )
        return response.choices[0].message["content"]
    result = get_completion(prompt)
    st.markdown(f"USF GenAI Assistant: {result}")
    
##BullBot

st.header("USFConnect 🐂 BullBot! How can I assist you today?")
chat_placeholder = st.container() # container for chat history
prompt_placeholder = st.form("chat-form") # chat-form is the key for this form. This is used to reference this form in other parts of the code
debug_placeholder = st.empty() # container for debugging information


# Create a delay function to check elapsed time using Streamlit's new caching mechanism
@st.cache_data(ttl=1)  # Cache data for 1 second
def delay():
    return time.time()

if "last_message_time" not in st.session_state:
    st.session_state.last_message_time = time.time()

if "feedback_shown" not in st.session_state:
    st.session_state.feedback_shown = False

with chat_placeholder:  # display chat history
    for chat in st.session_state.history:
        div = f"""
            <div class="chat-row {'' if chat.origin == 'ai' else 'row-reverse'}">
                <img class="chat-icon" src = "{'https://content.sportslogos.net/logos/34/837/full/south_florida_bulls_logo_secondary_20036111.png' if chat.origin == 'ai' else 'https://www.seekpng.com/png/detail/131-1316604_built-an-enhanced-lab-template-ppp-prd-045.png'}" width=60 height=60>
                <div class="chat-bubble {'ai-bubble' if chat.origin == 'ai' else 'human-bubble'}">
                    &#8203;{chat.message}
                </div>
            </div>
        """
        st.markdown(div, unsafe_allow_html=True)

    for _ in range(3):  # add a few blank lines between chat history and input field
        st.markdown("")

 # Check if 40 seconds have passed since the last message
    current_time = delay()
    if not st.session_state.feedback_shown and current_time - st.session_state.last_message_time > 40:
        feedback = st.radio("Has the conversation ended?", options=["Yes", "No"], index=None)
        if feedback:
            st.session_state.feedback_shown = True  # mark feedback as shown
            if feedback == "Yes":
                st.write("Thank you for your feedback!")
            elif feedback == "No":
                st.write("Please continue your conversation.")
                st.session_state.last_message_time = time.time()  # update the last message time


with prompt_placeholder: # this is the container for the chat input field
    col1, col2 = st.columns((6,1)) # col1 is 6 wide, and col2 is 1 wide
    col1.text_input(
        "Chat",
        value="Please enter your question here",
        label_visibility="collapsed",
        key="human_prompt",  # this is the key, which allows us to read the value of this text field later in the callback function
    )
    col2.form_submit_button(
        "Go Bulls!!",
        type="primary",
        on_click=on_click_callback,  # important! this set's the callback function for the submit button
    )
    
debug_placeholder.caption(  # display debugging information
    f"""
    Used {st.session_state.token_count} tokens \n
    Debug Langchain.coversation:
    {st.session_state.conversation.memory.buffer}
    """
    )


