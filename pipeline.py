from agents import build_search_agent, build_read_agent, build_writer_chain, build_critic_chain, build_followup_chain, get_llm
import logging

logger = logging.getLogger(__name__)

def run_research_pipeline(topic: str, llm) -> dict:
    state = {}

    writer_chain = build_writer_chain(llm)
    critic_chain = build_critic_chain(llm)

    # Search Agent
    logger.info("SEARCH AGENT WORKING...")
    try:
        search_agent = build_search_agent(llm)
        search_result = search_agent.invoke({
            "messages": [("user", f"Find the latest and most relevant information on the topic: {topic}")]
        })
        state["search_results"] = search_result["messages"][-1].content
    except Exception as e:
        logger.error(f"Search agent failed: {e}")
        state["search_results"] = f"Search failed: {str(e)}"

    # Reader Agent
    logger.info("READER AGENT IS SCRAPING TOP RESOURCES...")
    try:
        reader_agent = build_read_agent(llm)
        reader_result = reader_agent.invoke({
            "messages": [("user",
                f"You are a web scraper agent. The search results below contain URLs.\n"
                f"You MUST call the scrape_url tool with one of the URLs listed below.\n"
                f"Do NOT say you cannot find URLs — they are clearly listed after 'URL:' in each result.\n"
                f"Topic: {topic}\n\n"
                f"Search Results:\n{state['search_results'][:2000]}"
            )]
        })
        state["scraped_content"] = reader_result["messages"][-1].content
    except Exception as e:
        logger.error(f"Reader agent failed: {e}")
        state["scraped_content"] = f"Scraping failed: {str(e)}"

    # Writer Chain
    logger.info("WRITER CHAIN IS CREATING THE RESEARCH REPORT...")
    research_combined = (
        f"Search Results:\n{state['search_results']}\n\n"
        f"Scraped Content:\n{state['scraped_content']}"
    )
    try:
        state["report"] = writer_chain.invoke({
            "topic": topic,
            "research": research_combined,
        })
    except Exception as e:
        logger.error(f"Writer chain failed: {e}")
        raise RuntimeError(f"Report generation failed: {str(e)}")

    # Critic Chain
    logger.info("CRITIC CHAIN IS EVALUATING THE RESEARCH REPORT...")
    try:
        state["feedback"] = critic_chain.invoke({"report": state["report"]})
    except Exception as e:
        logger.error(f"Critic chain failed: {e}")
        state["feedback"] = f"Critic evaluation failed: {str(e)}"

    # Follow-up Questions
    logger.info("GENERATING FOLLOW-UP RESEARCH QUESTIONS...")
    try:
        followup_chain = build_followup_chain(llm)
        state["followup_questions"] = followup_chain.invoke({
            "topic": topic,
            "report": state["report"],
        })
    except Exception as e:
        logger.error(f"Followup chain failed: {e}")
        state["followup_questions"] = ""

    return state


if __name__ == "__main__":
    topic = input("\nEnter a research topic: ")
    llm = get_llm("Groq — Llama 3.3 70B", api_key=None)  # uses .env key by default
    result = run_research_pipeline(topic, llm)