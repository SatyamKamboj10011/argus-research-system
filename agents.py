from langchain.agents import create_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools import web_search, scrape_url
import os
from dotenv import load_dotenv

load_dotenv()

def get_llm(model_choice: str, api_key: str = None):
    print(f"DEBUG model_choice: '{model_choice}'")
    if model_choice == "Groq — Llama 3.3 70B":
        return ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key, temperature=0)
    elif model_choice == "Groq — Llama 3.1 8B":
        return ChatGroq(model="llama-3.1-8b-instant", api_key=api_key, temperature=0)
    elif model_choice == "Gemini — 2.0 Flash":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key, temperature=0)
    elif model_choice == "Cerebras — Llama 3.1 8B":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="llama3.1-8b",
            api_key=api_key,
            base_url="https://api.cerebras.ai/v1",
            temperature=0
    )
    elif model_choice == "Local — Ollama Llama 3":
         from langchain_ollama import ChatOllama
         return ChatOllama(model="llama3:latest", temperature=0)

    elif model_choice == "Local — Qwen 2.5 7B":
         from langchain_ollama import ChatOllama
         return ChatOllama(model="qwen2.5:7b", temperature=0)

    elif model_choice == "Local — Qwen 3.5":
         from langchain_ollama import ChatOllama
         return ChatOllama(model="qwen3.5:latest", temperature=0)
   
    else:
        # fallback
        return ChatGroq(model="llama-3.1-8b-instant", api_key=api_key, temperature=0)


# First AGENT
def build_search_agent(llm):
    return create_agent(
        model=llm,
        tools=[web_search],
    )

# Second AGENT
def build_read_agent(llm):
    return create_agent(
        model=llm,
        tools=[scrape_url],
    )


# Writer Chain
writer_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a senior research analyst and professional report writer with expertise in 
synthesizing complex information into clear, structured, and insightful reports.

Your writing must be:
- Factual and evidence-based — never speculate or fabricate information
- Well-structured with smooth transitions between sections
- Professional in tone, yet easy to understand
- Rich in detail, context, and analysis
- Properly sourced with references to all information used

If the research provided is insufficient for any section, explicitly state what is missing 
rather than filling gaps with assumptions."""),

    ("human", """Write a comprehensive, professional research report on the topic below.

Topic: {topic}

Research Gathered:
{research}

Your report MUST follow this exact structure:

---

## 1. Executive Summary
Provide a 3-5 sentence overview of the entire report — what was researched, 
what was found, and why it matters.

## 2. Introduction
- Background and context of the topic
- Why this topic is important or relevant today
- Scope and limitations of this research

## 3. Key Findings
Present a minimum of 5 well-explained findings. For each finding:
- Give it a clear heading
- Explain the finding in depth (at least 3-4 sentences)
- Back it up with data, facts, or evidence from the research
- Explain its significance or implications

## 4. Analysis & Insights
- Identify patterns, trends, or connections across the findings
- Provide your expert interpretation of what the research means
- Highlight any contradictions or gaps in the available information

## 5. Conclusion
- Summarize the most critical takeaways
- What should the reader remember or act on?
- Any recommendations or future outlook if applicable

## 6. Sources
- List every source used in the research
- Format: [Source Name] - [URL or reference]

---

Be detailed, factual, and professional. Aim for depth over brevity."""),
])

def build_writer_chain(llm):
    return writer_prompt | llm | StrOutputParser()


# Critic Chain
critic_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a ruthlessly objective senior research critic and quality assurance expert. 
Your role is to evaluate research reports with absolute honesty and precision.

You do NOT give inflated scores. A score of 10/10 means the report is virtually flawless.
A score below 5/10 means the report has serious quality issues.

You evaluate based on:
- Factual Accuracy: Are all claims backed by evidence? Any misinformation?
- Depth of Analysis: Does it go beyond surface-level? Are findings well-explained?
- Structure & Clarity: Is the report logically organized and easy to follow?
- Use of Sources: Are sources cited properly? Are they credible and relevant?
- Completeness: Does it fully address the topic without major gaps?
- Professional Quality: Is the writing polished and professional?"""),

    ("human", """Critically evaluate the following research report with strict, honest judgment.

Research Report:
{report}

Respond in EXACTLY this format — do not deviate:

---

Overall Score: X/10

Category Scores:
- Factual Accuracy:     X/10
- Depth of Analysis:    X/10
- Structure & Clarity:  X/10
- Use of Sources:       X/10
- Completeness:         X/10
- Professional Quality: X/10

Strengths:
- [Specific strength with explanation]
- [Specific strength with explanation]
- [Specific strength with explanation]

Critical Areas for Improvement:
- [Specific issue with explanation of why it matters]
- [Specific issue with explanation of why it matters]
- [Specific issue with explanation of why it matters]

Missing Elements:
- [What is absent from the report that should be there]

One-Line Verdict: [A single, sharp, honest sentence summarizing the report's overall quality]

Recommendation: [APPROVE / NEEDS REVISION / REJECT] — with a one sentence reason

---"""),
])


fact_checker_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert fact checker. Verify claims in the report against source material. Flag anything unverified, contradictory, or misleading."),
    ("human", """Fact check this report against the sources.

Report: {report}
Sources: {research}

---
Verified Claims:
- ...

Unverified Claims:
- [claim] — Reason: ...

Contradictions:
- [contradiction] — Source says: ...

Fact Check Score: X/10
Verdict: [RELIABLE / MOSTLY RELIABLE / USE WITH CAUTION / UNRELIABLE]
---"""),
])

followup_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a research assistant. Generate insightful follow-up questions based on gaps and interesting points in the report."),
    ("human", """Generate 5 follow-up research questions for this topic.

Topic: {topic}
Report: {report}

---
1. ...
2. ...
3. ...
4. ...
5. ...
---"""),
])

credibility_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert at evaluating source credibility based on authority, accuracy, currency, and bias."),
    ("human", """Rate the credibility of these sources.

Sources: {search_results}

---
[URL]
- Score: X/10
- Strengths: ...
- Weaknesses: ...

Overall Quality: X/10
Verdict: [HIGHLY RELIABLE / RELIABLE / MIXED / POOR]
---"""),
])

def build_critic_chain(llm):
    return critic_prompt | llm | StrOutputParser()


def build_fact_checker_chain(llm):
    return fact_checker_prompt | llm | StrOutputParser()

def build_followup_chain(llm):
    return followup_prompt | llm | StrOutputParser()

def build_credibility_chain(llm):
    return credibility_prompt | llm | StrOutputParser()