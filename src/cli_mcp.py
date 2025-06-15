import asyncio
import logging
import json
import sys
import os
from datetime import datetime

print("🚀 Starting WebMCP CLI...")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from browser.automation import BrowserAutomation
from llm.client import get_llm_response

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_MCP = """You are an AI assistant that controls a web browser based on a Model Context Protocol (MCP).
Your goal is to achieve the user's stated 'user_goal'.

CRITICAL COMPLETION RULES:
- IMMEDIATELY use "goal_achieved" action after taking a screenshot if the user requested one
- IMMEDIATELY use "goal_achieved" action after successfully retrieving information the user requested
- NEVER repeat the same action type twice in a row unless it failed
- If you take a screenshot, that task is COMPLETE - use "goal_achieved" immediately after
- If you get page content successfully, that task is COMPLETE - use "goal_achieved" immediately after

CRITICAL:
- For Google search: After typing a query into 'textarea[name="q"]', ALWAYS use the 'press_key' action with key 'Enter' and selector 'textarea[name="q"]' to submit the search.
- For Google Weather: After submitting the search, wait for the weather widget selector '#wob_tm' (temperature) to be visible before extracting it. If not found, try '#wob_dc' (description) or get the text content of the main results area.
- If a step to get information fails, DO NOT proceed as if you have the information. Try an alternative selector or method, or use 'clarify' if you are stuck.
- ONLY use the "take_screenshot" action if the user's goal EXPLICITLY asks for a screenshot or if it's essential to confirm a visual change for a complex task. Avoid screenshots for simple information retrieval.
- If the goal is to find specific information (e.g., weather, stock price), ensure the 'get_page_text_content' action for that specific information SUCCEEDS before using 'goal_achieved'. If it fails, do not use 'goal_achieved' with a placeholder.

Based on the context, decide the next single best action or a short sequence of actions (max 3 actions).
Output these actions as a JSON list. Each action MUST be an object with EXACTLY "action_type" and "parameters".

SUPPORTED ACTION TYPES (use EXACTLY these names):
1. "navigate": parameters: {"url": "string"}
2. "click_element": parameters: {"selector": "CSS selector string"}
3. "type_into_element": parameters: {"selector": "CSS selector string", "text": "string to type"}
4. "select_dropdown_option": parameters: {"selector": "CSS selector string", "option_value": "string"}
5. "check_checkbox": parameters: {"selector": "CSS selector string", "checked": true/false}
6. "upload_file": parameters: {"selector": "CSS selector string", "file_path": "string"}
7. "hover_element": parameters: {"selector": "CSS selector string"}
8. "scroll_page": parameters: {"direction": "up/down/left/right", "pixels": number}
9. "press_key": parameters: {"key": "string", "selector": "CSS selector string (optional)"}
10. "wait_for_element": parameters: {"selector": "CSS selector string", "timeout_ms": number, "state": "visible/hidden/attached"}
11. "get_page_text_content": parameters: {"selector": "CSS selector string (optional)"}
12. "get_element_attribute": parameters: {"selector": "CSS selector string", "attribute": "string"}
13. "take_screenshot": parameters: {"filename": "string (optional)", "full_page": true/false}
14. "find_element_by_description": parameters: {"description": "string describing what to find"}
15. "clarify": parameters: {"question": "string - ask user for clarification"}
16. "goal_achieved": parameters: {"summary_of_findings": "string (optional, if information was successfully retrieved and is NOT a placeholder)"}

CRITICAL JSON FORMAT REQUIREMENTS:
- ALWAYS use "action_type" (not "action", "type", or anything else)
- ALWAYS use "parameters" (not "params", "args", or anything else)
- Return ONLY the JSON array, no other text

CORRECT EXAMPLE:
[{"action_type": "navigate", "parameters": {"url": "https://www.google.com"}}]

INCORRECT EXAMPLES (DO NOT USE):
[{"action": "navigate", "url": "https://www.google.com"}]
[{"type": "navigate", "parameters": {"url": "https://www.google.com"}}]

IMPORTANT GUIDELINES:
- For Google search: Use textarea[name='q'] for the search box.
- For Google Weather: After searching, always press Enter, then wait for '#wob_tm' (temperature). If not found, try '#wob_dc' (description) or get the text content of the main results area.
- If 'get_page_text_content' for crucial info fails, DO NOT use 'goal_achieved' with a placeholder like '[weather_information]'. Instead, try another selector, or use 'clarify' or indicate failure.
- Use "take_screenshot" SPARINGLY.

Output ONLY the JSON list of actions. No explanatory text before or after.
"""

SYSTEM_PROMPT_FINAL_ANSWER = """You are an AI assistant. Based on the user's original goal and the gathered information or actions performed, provide a concise, direct answer.
- If the goal was to find information and it was successfully retrieved (e.g., in 'summary_of_findings' or 'last_page_text_content'), state that information clearly.
- If the information contains placeholders like '[some_information]', or if the context indicates the information could not be found, explicitly state that the information could not be retrieved.
- If the goal was to perform an action, confirm its completion or state if it failed.
Be brief and accurate.
"""

def extract_and_display_info(text_content: str, user_goal: str):
    if not text_content:
        return
    
    goal_lower = user_goal.lower()
    
    if any(keyword in goal_lower for keyword in ['stock', 'price', 'share', 'nasdaq', 'nyse', 'trading']):
        import re
        
        price_patterns = [
            r'\$\s*(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',
            r'USD\s*(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d{1,4}(?:,\d{3})*\.\d{2})\s*USD',
            r'Price:\s*\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',
            r'Current:\s*\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        found_prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            found_prices.extend(matches)
        
        if found_prices:
            print(f"\n💰 STOCK PRICE FOUND: ${found_prices[0]}")
            print(f"🔍 Source: Page content analysis")
    
    elif any(keyword in goal_lower for keyword in ['weather', 'temperature', 'climate', 'forecast']):
        import re
        
        temp_patterns = [
            r'(\d{1,3})°[CF]',
            r'(\d{1,3})\s*degrees',
            r'Temperature:\s*(\d{1,3})',
        ]
        
        found_temps = []
        for pattern in temp_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            found_temps.extend(matches)
        
        if found_temps:
            print(f"\n🌡️ TEMPERATURE FOUND: {found_temps[0]}°")
            print(f"🔍 Source: Weather widget analysis")
    
    elif any(keyword in goal_lower for keyword in ['search', 'find', 'get', 'what', 'information']):
        lines = text_content.split('\n')
        meaningful_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10]
        if meaningful_lines:
            print(f"\n📄 INFORMATION FOUND:")
            print(f"   {meaningful_lines[0][:100]}...")
            print(f"🔍 Source: Page content analysis")

async def mcp_loop(user_goal: str, headless: bool = True, max_iterations: int = 25) -> dict:
    logger.info(f"Starting MCP for goal: {user_goal}")
    
    interaction_context = {
        "user_goal": user_goal,
        "history": [],
        "current_page_url": None,
        "last_error": None,
        "last_page_text_content": None,
        "final_answer_to_goal": None,
        "summary_from_goal_achieved": None,
        "information_retrieved_successfully": False,
        "screenshot_taken": False,
        "task_completed": False,
        "last_action_type": None,
        "action_repeat_count": 0
    }
    
    async with BrowserAutomation(headless=headless) as browser:
        for iteration in range(1, max_iterations + 1):
            logger.info(f"\nMCP Iteration: {iteration}/{max_iterations}. Goal: {user_goal}")
            
            if interaction_context["task_completed"]:
                logger.info("MCP: Task marked as completed, exiting loop")
                break
            
            mcp_prompt_for_llm = f"User Goal: {user_goal}\n"
            if iteration == 1:
                mcp_prompt_for_llm += "This is the first iteration. Browser is ready. What is the first action?"
            else:
                history_summary = "\n".join([
                    f"Action: {h['action_taken'].get('action_type', 'unknown')} -> Result: {h['outcome']['status']}" +
                    (f" ({h['outcome']['message']})" if h['outcome'].get('message') else "")
                    for h in interaction_context["history"][-3:]
                ])
                page_content_info = f"\nLast successfully retrieved page content (first 1000 chars):\n{interaction_context.get('last_page_text_content', '')[:1000]}..." if interaction_context.get('last_page_text_content') else "\nNo page content successfully retrieved yet."
                
                completion_info = f"\nScreenshot taken: {interaction_context['screenshot_taken']}\nLast action: {interaction_context['last_action_type']}\nAction repeat count: {interaction_context['action_repeat_count']}"
                
                mcp_prompt_for_llm += f"""Current page: {interaction_context.get('current_page_url', 'Unknown')}
Iteration: {iteration}/{max_iterations}
Last error: {interaction_context.get('last_error', 'None')}
Information retrieved successfully so far: {interaction_context['information_retrieved_successfully']}
{completion_info}
Recent actions:
{history_summary}
{page_content_info}
What should be the next action(s)? If specific information was successfully retrieved and it answers the goal, use 'goal_achieved' with 'summary_of_findings' containing the ACTUAL information. If a data retrieval step failed, do not use 'goal_achieved' with a placeholder.
IMPORTANT: If you just took a screenshot and user requested one, use 'goal_achieved' IMMEDIATELY. If you retrieved information successfully, use 'goal_achieved' IMMEDIATELY.
REMEMBER: Return ONLY a JSON array. Use "take_screenshot" sparingly.
"""
            
            actions_to_execute_json_str = get_llm_response(SYSTEM_PROMPT_MCP, mcp_prompt_for_llm)
            
            if not actions_to_execute_json_str:
                logger.error("MCP: Could not get an action plan from LLM.")
                if iteration > 1:
                    logger.info("MCP: Fallback - taking screenshot for debugging if stuck.")
                    await browser.take_screenshot(f"debug_iter_{iteration}_stuck.png")
                await asyncio.sleep(2)
                continue
            
            try: 
                actions_to_execute = json.loads(actions_to_execute_json_str)
                if not isinstance(actions_to_execute, list): actions_to_execute = [actions_to_execute]
                for action in actions_to_execute:
                    if not isinstance(action, dict): raise ValueError(f"Action not a dict: {type(action)}")
                    if "action_type" not in action:
                        if "action" in action: action["action_type"] = action.pop("action"); logger.warning("Fixed 'action'->'action_type'")
                        elif "type" in action: action["action_type"] = action.pop("type"); logger.warning("Fixed 'type'->'action_type'")
                        else: raise ValueError(f"Action missing 'action_type': {action}")
                    if "parameters" not in action:
                        action["parameters"] = {k: v for k, v in action.items() if k not in ["action_type", "parameters"]}
                        for k_orig in list(action["parameters"].keys()): action.pop(k_orig)
                        logger.warning(f"Fixed parameters for: {action['action_type']}")
                logger.info(f"MCP: LLM Action Plan:\n{json.dumps(actions_to_execute, indent=2)}")
            except Exception as e:
                logger.error(f"MCP: JSON/Action validation error: {e}. Raw: {actions_to_execute_json_str}")
                await asyncio.sleep(2)
                continue

            for action_idx, action in enumerate(actions_to_execute):
                action_type = action.get("action_type")
                parameters = action.get("parameters", {})
                logger.info(f"MCP: Executing ({action_idx+1}/{len(actions_to_execute)}): {action_type} with {parameters}")

                if action_type == interaction_context["last_action_type"]:
                    interaction_context["action_repeat_count"] += 1
                    if interaction_context["action_repeat_count"] >= 3:
                        logger.warning(f"MCP: Detected potential infinite loop with action '{action_type}', forcing completion")
                        interaction_context["task_completed"] = True
                        interaction_context["summary_from_goal_achieved"] = f"Task completion forced due to repeated actions. Last successful action was {action_type}."
                        break
                else:
                    interaction_context["last_action_type"] = action_type
                    interaction_context["action_repeat_count"] = 1

                if action_type == "clarify":
                    question = parameters.get("question", "More info needed.")
                    print(f"\n❓ LLM Clarification: {question}")
                    user_response = input("Your response: ")
                    interaction_context["history"].append({"action_taken": action, "outcome": {"status": "success", "message": f"User: {user_response}"}})
                    interaction_context["last_page_text_content"] = f"User clarification: {user_response}"
                    interaction_context["information_retrieved_successfully"] = False
                    continue
                
                if action_type == "goal_achieved":
                    logger.info("MCP: LLM indicated goal achieved.")
                    interaction_context["summary_from_goal_achieved"] = parameters.get("summary_of_findings")
                    interaction_context["task_completed"] = True
                    
                    if interaction_context["summary_from_goal_achieved"] and "[" in interaction_context["summary_from_goal_achieved"] and "]" in interaction_context["summary_from_goal_achieved"]:
                        logger.warning(f"Goal achieved called with placeholder summary: {interaction_context['summary_from_goal_achieved']}. Will indicate failure to retrieve info.")
                        interaction_context["information_retrieved_successfully"] = False
                    elif interaction_context["summary_from_goal_achieved"]:
                         interaction_context["information_retrieved_successfully"] = True

                    final_answer_prompt_context = f"User's original goal: '{user_goal}'\n"
                    if interaction_context["information_retrieved_successfully"] and interaction_context["summary_from_goal_achieved"]:
                        final_answer_prompt_context += f"The AI performing the web task provided this summary: '{interaction_context['summary_from_goal_achieved']}'\n"
                    elif interaction_context["information_retrieved_successfully"] and interaction_context["last_page_text_content"]:
                         final_answer_prompt_context += f"The following information was gathered from the last page:\n---\n{interaction_context['last_page_text_content'][:2000]}\n---\n"
                    else:
                        final_answer_prompt_context += "The necessary information could not be successfully retrieved from the webpage.\n"
                    final_answer_prompt_context += "Based on this, what is the direct answer to the user's goal? If the goal was an action, confirm its completion. If info was not found, state that."
                    
                    synthesized_answer = get_llm_response(SYSTEM_PROMPT_FINAL_ANSWER, final_answer_prompt_context, is_final_answer_generation=True)
                    interaction_context["final_answer_to_goal"] = synthesized_answer if synthesized_answer else "Goal marked as achieved by AI, but could not synthesize a final textual answer."
                    
                    final_summary = generate_result_summary(interaction_context, iteration)
                    print(final_summary)
                    return {
                        "status": "success" if interaction_context["information_retrieved_successfully"] else "partial_failure", 
                        "message": "Goal processing complete.",
                        "iterations_used": iteration, "actions_completed": len(interaction_context["history"]),
                        "summary": final_summary, "final_answer": interaction_context["final_answer_to_goal"]
                    }

                result = await execute_browser_action(browser, action_type, parameters)
                interaction_context["history"].append({"action_taken": action, "outcome": result})
                
                if result['status'] == 'success':
                    interaction_context["last_error"] = None
                    if action_type == "navigate": 
                        interaction_context["current_page_url"] = result.get('url', parameters.get('url'))
                        interaction_context["last_page_text_content"] = None
                        interaction_context["information_retrieved_successfully"] = False
                        print(f"\n🌐 Navigated to: {interaction_context['current_page_url']}")
                    elif action_type == "get_page_text_content":
                        text_content = result.get('result', {}).get('text_content', '')
                        if text_content:
                            interaction_context["last_page_text_content"] = text_content
                            interaction_context["information_retrieved_successfully"] = True
                            logger.info(f"📄 Page content captured: {len(text_content)} chars.")
                            
                            extract_and_display_info(text_content, user_goal)
                            
                            if any(keyword in user_goal.lower() for keyword in ['search', 'find', 'get', 'what', 'weather', 'price', 'information']):
                                logger.info("MCP: Information retrieval goal detected and completed")
                                interaction_context["task_completed"] = True
                                interaction_context["summary_from_goal_achieved"] = f"Successfully retrieved information: {text_content[:200]}..."
                        else:
                            logger.warning("MCP: get_page_text_content returned empty. Info not retrieved.")
                            interaction_context["information_retrieved_successfully"] = False
                    elif action_type == "take_screenshot":
                        interaction_context["screenshot_taken"] = True
                        screenshot_path = result.get('filepath', 'screenshot completed')
                        print(f"\n📸 Screenshot saved: {screenshot_path}")
                        if 'screenshot' in user_goal.lower():
                            logger.info("MCP: Screenshot goal detected and completed")
                            interaction_context["task_completed"] = True
                            interaction_context["summary_from_goal_achieved"] = f"Successfully took screenshot: {screenshot_path}"
                            interaction_context["information_retrieved_successfully"] = True
                else:
                    interaction_context["last_error"] = result.get('message', 'Unknown error')
                    interaction_context["information_retrieved_successfully"] = False
                
                logger.info(f"MCP: Result ({action_type}): {result['status']}" + (f" - {result['message']}" if result.get('message') else ""))
                await asyncio.sleep(0.5)
                
                if interaction_context["task_completed"]:
                    logger.info("MCP: Task completed automatically, breaking action loop")
                    break
            
            if interaction_context["task_completed"]:
                break
                
            await asyncio.sleep(1) 
        
        if not interaction_context["task_completed"]:
            logger.warning("MCP: Max iterations reached.")
            final_answer_prompt_context = f"User's original goal: '{user_goal}'\nTask ended after {max_iterations} iterations.\n"
            if interaction_context["information_retrieved_successfully"] and interaction_context["last_page_text_content"]:
                final_answer_prompt_context += f"Information from last page:\n{interaction_context['last_page_text_content'][:2000]}\n\n"
            else:
                final_answer_prompt_context += "The necessary information could not be successfully retrieved within the allowed iterations.\n"
            final_answer_prompt_context += "Answer the goal based on available info, or state what was done and that max iterations were reached and info might be missing."
            
            synthesized_answer = get_llm_response(SYSTEM_PROMPT_FINAL_ANSWER, final_answer_prompt_context, is_final_answer_generation=True)
            interaction_context["final_answer_to_goal"] = synthesized_answer if synthesized_answer else "Max iterations reached; could not synthesize a final answer."

            final_summary = generate_result_summary(interaction_context, max_iterations)
            print(final_summary)
            return {
                "status": "max_iterations_reached", "iterations_used": max_iterations,
                "actions_completed": len(interaction_context["history"]),
                "message": f"Completed {len(interaction_context['history'])} actions in {max_iterations} iterations.",
                "summary": final_summary, "final_answer": interaction_context["final_answer_to_goal"]
            }
        else:
            final_answer_prompt_context = f"User's original goal: '{user_goal}'\n"
            if interaction_context["summary_from_goal_achieved"]:
                final_answer_prompt_context += f"Task completed: {interaction_context['summary_from_goal_achieved']}\n"
            elif interaction_context["screenshot_taken"]:
                final_answer_prompt_context += "Screenshot was taken successfully.\n"
            elif interaction_context["information_retrieved_successfully"]:
                final_answer_prompt_context += f"Information was retrieved: {interaction_context['last_page_text_content'][:500] if interaction_context['last_page_text_content'] else 'Content available'}\n"
            
            synthesized_answer = get_llm_response(SYSTEM_PROMPT_FINAL_ANSWER, final_answer_prompt_context, is_final_answer_generation=True)
            interaction_context["final_answer_to_goal"] = synthesized_answer if synthesized_answer else "Task completed automatically."

            final_summary = generate_result_summary(interaction_context, iteration)
            print(final_summary)
            return {
                "status": "success", "iterations_used": iteration,
                "actions_completed": len(interaction_context["history"]),
                "message": "Task completed successfully.",
                "summary": final_summary, "final_answer": interaction_context["final_answer_to_goal"]
            }

def generate_result_summary(context, iterations_used):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    final_answer = context.get("final_answer_to_goal", "Not synthesized.")
    info_retrieved_successfully = context.get("information_retrieved_successfully", False)
    
    status_text = "⚠️ PARTIAL/CHECK"
    if context.get("last_error") is None and "Could not synthesize" not in final_answer and "Max iterations reached" not in final_answer:
        if info_retrieved_successfully or "Goal marked as achieved by AI" in final_answer or "confirm its completion" in final_answer.lower() or "task completed" in final_answer.lower() :
             if not ("could not be retrieved" in final_answer.lower() or "unable to find" in final_answer.lower() or "[some_information]" in final_answer or "[weather_information]" in final_answer):
                status_text = "✅ SUCCESS"

    summary = f"""
╔═══════════════════════════════════════════════════════════════╗
║                    🎯 WebMCP AUTOMATION RESULT                ║
╠═══════════════════════════════════════════════════════════════╣
║ 📅 Completed: {current_time}                            ║
║ 🎯 Goal: {context['user_goal'][:45]:<45} ║
║ 🔄 Iterations: {iterations_used:<8} Max: 25                     ║
║ ⚡ Actions: {len(context['history']):<6}                                  ║
║ 🌐 Final URL: {(context.get('current_page_url', 'N/A'))[:43]:<43} ║
║ 📊 Status: {status_text:<43} ║
╠═══════════════════════════════════════════════════════════════╣
║ 💬 FINAL ANSWER TO GOAL:                                      ║
║ >> {final_answer[:60]:<60} ║"""
    if len(final_answer) > 60:
        summary += f"""
║    {final_answer[60:120]:<60} ║"""
    if len(final_answer) > 120:
        summary += f"""
║    ... (see full answer above/below)                         ║"""
    summary += f"""
╠═══════════════════════════════════════════════════════════════╣
║                      🤖 AI MODELS USED                        ║
║ • Gemini Flash 2.0 (Primary)                                 ║
║ • Mistral 7B Instruct (Secondary)                            ║
║ • Llama 3.2 / DeepSeek (Backups)                             ║
╠═══════════════════════════════════════════════════════════════╣
║                     📋 RECENT ACTIONS                         ║"""
    
    for i, action_log in enumerate(context["history"][-3:], 1): 
        action_type = action_log["action_taken"].get("action_type", "unknown")
        status_icon = "✅" if action_log["outcome"]["status"] == "success" else "❌"
        summary += f"""
║ {i}. {status_icon} {action_type:<25} {action_log["outcome"]["status"]:<12} ║"""
    if len(context["history"]) > 3: summary += f"""
║    ... and {len(context['history']) - 3} more actions earlier                     ║"""
    
    summary += f"""
╠═══════════════════════════════════════════════════════════════╣
║                    🎬 DEMO VIDEO READY                        ║
║ • Screenshots in: screenshots/ (if requested)                ║
║ • Final Answer Display: IMPLEMENTED                          ║
║ • Loop Prevention: ACTIVE                                    ║
║ • Real-time Info Display: ENABLED                           ║
╚═══════════════════════════════════════════════════════════════╝
"""
    return summary

async def execute_browser_action(browser: BrowserAutomation, action_type: str, parameters: dict) -> dict:
    try:
        if action_type == "navigate": return await browser.navigate(parameters["url"])
        elif action_type == "click_element": return await browser.click_element(parameters["selector"])
        elif action_type == "type_into_element": return await browser.type_into_element(parameters["selector"], parameters["text"])
        elif action_type == "select_dropdown_option": return await browser.select_dropdown_option(parameters["selector"], parameters["option_value"])
        elif action_type == "check_checkbox": return await browser.check_checkbox(parameters["selector"], parameters.get("checked", True))
        elif action_type == "upload_file": return await browser.upload_file(parameters["selector"], parameters["file_path"])
        elif action_type == "hover_element": return await browser.hover_element(parameters["selector"])
        elif action_type == "scroll_page": return await browser.scroll_page(parameters["direction"], parameters.get("pixels", 300))
        elif action_type == "press_key":
            return await browser.press_key(parameters["key"], parameters.get("selector"))
        elif action_type == "wait_for_element":
            return await browser.wait_for_element(parameters["selector"], parameters.get("timeout_ms", 10000), parameters.get("state", "visible"))
        elif action_type == "get_page_text_content": return await browser.get_page_text_content(parameters.get("selector"))
        elif action_type == "get_element_attribute": return await browser.get_element_attribute(parameters["selector"], parameters["attribute"])
        elif action_type == "take_screenshot": return await browser.take_screenshot(parameters.get("filename"), parameters.get("full_page", False))
        elif action_type == "find_element_by_description": return await browser.find_element_by_description(parameters["description"])
        else: return {"status": "error", "message": f"Unknown action type: {action_type}"}
    except Exception as e:
        logger.error(f"MCP: Action '{action_type}' failed: {e}")
        return {"status": "error", "message": str(e)}

async def test_login_prompt(headless: bool = False):
    test_goal = "Go to Instagram and login with username 'testuser123' and password 'testpass456', then take a screenshot"
    logger.info(f"Running test login prompt: {test_goal}")
    return await mcp_loop(test_goal, headless=headless)

async def main_cli():
    print("WebMCP CLI - Type your command/goal or 'exit'. 'test_login' for Instagram test.")
    while True:
        try:
            goal = input("\nGoal or 'test_login'/'exit'> ").strip()
            if goal.lower() == 'exit': 
                print("Exiting...")
                break
            elif goal.lower() == 'test_login':
                print("🧪 Running test login prompt...")
                final_result = await test_login_prompt(headless=False)
            elif goal: 
                final_result = await mcp_loop(user_goal=goal, headless=False, max_iterations=25)
            else: 
                print("Please enter a goal or 'exit'.")
                continue
            
            print(f"\n🏁 MCP Task Concluded for Goal: '{goal}'")
            if final_result.get("final_answer"):
                print(f"💬 AI's Answer to Your Goal: {final_result['final_answer']}")
            
            status_msg = final_result.get('status', 'unknown').replace('_', ' ').title()
            print(f"📊 Overall Status: {status_msg}")
            print(f"   Actions completed: {final_result.get('actions_completed', 'N/A')}, Iterations: {final_result.get('iterations_used', 'N/A')}")
            
        except KeyboardInterrupt: 
            print("\nOperation cancelled.")
            break
        except Exception as e: 
            logger.error(f"CLI Error: {e}")
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("✅ WebMCP CLI initialized successfully!")
    asyncio.run(main_cli())