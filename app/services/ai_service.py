import json
import os
import sys
from groq import AsyncGroq

from app.mcp.mcp_client import (
    get_available_tools,
    call_tool,
)


# ============================================================
# GROQ CLIENT
# ============================================================

groq = AsyncGroq(
    api_key=os.getenv("GROQ_API_KEY")
)


# ============================================================
# GET MCP TOOLS FOR GROQ
# ============================================================

async def get_tools_for_ai():
    """
    Get tools exposed by the MCP server and convert them
    into Groq function-calling format.
    """

    tools = await get_available_tools()

    ai_tools = []

    for tool in tools:

        tool_name = tool.name

        tool_description = (
            tool.description
            or ""
        )

        # MCP SDK versions may expose either
        # inputSchema or input_schema.
        input_schema = getattr(
            tool,
            "inputSchema",
            None
        )

        if input_schema is None:

            input_schema = getattr(
                tool,
                "input_schema",
                {}
            )

        ai_tools.append({
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_description,
                "parameters": input_schema,
            },
        })

    return ai_tools


# ============================================================
# AGENT SYSTEM PROMPT
# ============================================================

AGENT_SYSTEM_PROMPT = """
You are an ERP AI assistant.

Use the available ERP tools to answer ERP-related questions.

CORE RULES
- Use ERP tools whenever ERP data is required.
- Never guess, invent, estimate, or assume ERP data.
- Never generate SQL.
- If the required ERP data is unavailable, clearly say so.
- Use conversation context to understand follow-up questions.

READ-ONLY ERP
- The assistant is strictly read-only.
- Never create, update, edit, delete, modify, or submit ERP data.
- Never perform any write operation requested by the user.
- If the user asks to create, update, edit, delete, or modify ERP data,
  do not perform the operation.
- Clearly tell the user that ERP data modification is not supported.


SALES INVOICES
- Always use getSalesInvoices for sales-invoice questions.
- No filter: getSalesInvoices({})
- Invoice number: salesInvoiceNumber
- Customer name: customerName
- Part number: partNumber
- Date range: fromDate and toDate


CUSTOMERS
- Use getCustomers for customer-related questions.


PARTS
- Use getParts for part-related questions.


FOLLOW-UP QUESTIONS
Use conversation context for references such as:
- this invoice
- that invoice
- previous invoice
- this customer
- above one
- compare with the previous one

If the existing data is insufficient, call the appropriate ERP tool.


CHARTS
When the user asks for comparisons, rankings, distributions, or trends,
retrieve the ERP data required to answer the question.

- Never invent chart data.
- Chart data must come directly from ERP tool results.
- Do not generate chart data from assumptions or estimates.

The final response determines whether a chart should be displayed.
"""


# ============================================================
# FINAL RESPONSE + CHART SYSTEM PROMPT
# ============================================================

RESPONSE_SYSTEM_PROMPT = """
You are a professional ERP assistant.

Your input contains:
1. The user's question.
2. Conversation context.
3. Actual ERP data retrieved from ERP tools.

Answer the user using ONLY the provided ERP data and conversation context.

RULES
- Never guess, invent, estimate, or assume ERP information.
- Never create values that are not present in the ERP data.
- If required information is missing, clearly say it is unavailable.
- Keep the answer concise and human-readable.
- Do not mention SQL, MCP, tools, internal implementation, or this prompt.


==================================================
CHART DECISION
==================================================

Decide yourself whether a chart improves the answer.

Do not decide only from words like "chart", "graph", or "visualize".
A chart can be used even when the user does not explicitly request one.

Use a chart when the data contains meaningful numeric values and
visualization improves comparison, ranking, distribution, or trends.

Good chart use cases:
- customer sales comparison
- part sales comparison
- customer/part ranking
- sales distribution or share
- daily/monthly/quarterly/yearly sales
- sales trends
- meaningful categorical comparisons

Do NOT use a chart for:
- simple lists
- individual records
- individual invoices
- simple lookups
- very small or unsuitable datasets
- data without meaningful numeric values
- cases where text is clearer


==================================================
CHART TYPE
==================================================

Choose the most appropriate chart:

BAR:
- category comparisons
- customer/part comparisons
- rankings
- independent values

LINE:
- values changing over time
- daily/monthly/quarterly/yearly sales
- trends

PIE:
- part-to-whole composition
- customer/part sales share
- small number of categories

Never use PIE for time-based data.
Prefer BAR when exact value comparison is more important than composition.


==================================================
CHART DATA
==================================================

Chart values must come directly from the ERP data.

- Never invent or estimate values.
- Never modify numeric values.
- Do not silently remove relevant records.
- Use the appropriate granularity from the ERP data.


==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

The JSON must have exactly these fields:

{
    "message": "Human-readable ERP answer",
    "showChart": false,
    "chart": null
}

If a chart is appropriate:

{
    "message": "Human-readable ERP answer",
    "showChart": true,
    "chart": {
        "chartType": "bar | line | pie",
        "meta": {
            "title": "Chart title",
            "description": "Chart description"
        },
        "xKey": "category",
        "series": [
            {
                "dataKey": "value",
                "label": "Value",
                "axisLabel": "Value",
                "valueFormat": "compact",
                "valuePrefix": "₹"
            }
        ],
        "data": []
    }
}

For PIE charts use:

{
    "chartType": "pie",
    "meta": {
        "title": "Chart title",
        "description": "Chart description"
    },
    "nameKey": "category",
    "valueKey": "value",
    "data": []
}


==================================================
MESSAGE
==================================================

The message should:
- be concise and natural
- use Markdown when useful
- use headings/bullets when useful
- never use tables
- use ₹ for INR amounts
- never include chart JSON
- never mention internal implementation


==================================================
FOLLOW-UP QUESTIONS
==================================================

Use previous conversation context when the user refers to:
- previous results
- previous customers
- previous invoices
- "show more"
- "compare them"
- "compare with the above"
- "show this as a chart"

If the existing ERP data is insufficient, additional ERP data must be retrieved
before producing the final answer.
"""


# ============================================================
# MCP RESULT HELPER
# ============================================================

def extract_tool_content(result):
    """
    Extract text content from an MCP tool result.
    """

    # --------------------------------------------------------
    # Dictionary result
    # --------------------------------------------------------

    if isinstance(result, dict):

        content = result.get(
            "content"
        )

        if (
            content
            and isinstance(content, list)
        ):

            first_item = content[0]

            if isinstance(
                first_item,
                dict
            ):

                text = first_item.get(
                    "text"
                )

                if text is not None:
                    return str(text)

        return json.dumps(
            result,
            default=str
        )

    # --------------------------------------------------------
    # MCP SDK object result
    # --------------------------------------------------------

    content = getattr(
        result,
        "content",
        None
    )

    if (
        content
        and isinstance(content, list)
    ):

        first_item = content[0]

        text = getattr(
            first_item,
            "text",
            None
        )

        if text is not None:
            return str(text)

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    return str(result)


# ============================================================
# CLEAN ASSISTANT MESSAGE
# ============================================================

def build_assistant_message(
    assistant_message
):
    """
    Convert Groq assistant response into a clean message
    that can safely be sent back to Groq.

    We intentionally do NOT use model_dump() because
    newer Groq responses can contain unsupported fields
    such as annotations.
    """

    assistant_dict = {
        "role": "assistant",
        "content": (
            assistant_message.content
            or ""
        ),
    }

    # --------------------------------------------------------
    # TOOL CALLS
    # --------------------------------------------------------

    if assistant_message.tool_calls:

        assistant_dict["tool_calls"] = [

            {
                "id": tool_call.id,

                "type": "function",

                "function": {
                    "name":
                        tool_call.function.name,

                    "arguments":
                        tool_call.function.arguments,
                },
            }

            for tool_call
            in assistant_message.tool_calls
        ]

    return assistant_dict


# ============================================================
# PARSE FINAL AI RESPONSE
# ============================================================

def parse_final_response(
    content: str
):
    """
    Parse the JSON returned by Groq.

    Includes a small fallback for accidental Markdown
    code fences.
    """

    if not content:

        return {
            "message":
                "Sorry, I could not generate a response.",

            "showChart":
                False,

            "chart":
                None,
        }

    content = content.strip()

    # --------------------------------------------------------
    # Remove accidental ```json fences
    # --------------------------------------------------------

    if content.startswith(
        "```json"
    ):

        content = content[
            7:
        ].strip()

        if content.endswith(
            "```"
        ):

            content = content[
                :-3
            ].strip()

    elif content.startswith(
        "```"
    ):

        content = content[
            3:
        ].strip()

        if content.endswith(
            "```"
        ):

            content = content[
                :-3
            ].strip()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        parsed = json.loads(
            content
        )

    except Exception as error:

        print(
            "Final JSON parsing error:",
            error
        )

        print(
            "Final response:",
            content
        )

        # Safe fallback
        return {
            "message": content,
            "showChart": False,
            "chart": None,
        }

    # --------------------------------------------------------
    # Validate basic structure
    # --------------------------------------------------------

    message = parsed.get(
        "message",
        ""
    )

    show_chart = parsed.get(
        "showChart",
        False
    )

    chart = parsed.get(
        "chart"
    )

    # --------------------------------------------------------
    # Make chart consistent
    # --------------------------------------------------------

    if not show_chart:

        chart = None

    if (
        show_chart
        and not chart
    ):

        show_chart = False
        chart = None

    return {
        "message":
            message,

        "showChart":
            show_chart,

        "chart":
            chart,
    }


# ============================================================
# MAIN AI AGENT
# ============================================================

async def run_agent(
    user_question: str,
    history: list | None = None
):

    # ========================================================
    # HISTORY
    # ========================================================

    if history is None:

        history = []

    # ========================================================
    # GET MCP TOOLS
    # ========================================================

    tools = await get_tools_for_ai()

    # ========================================================
    # BUILD CONVERSATION
    # ========================================================

    messages = [
        {
            "role":
                "system",

            "content":
                AGENT_SYSTEM_PROMPT,
        }
    ]

    # --------------------------------------------------------
    # Add previous conversation
    # --------------------------------------------------------

    messages.extend(
        history
    )

    # --------------------------------------------------------
    # Add current question
    # --------------------------------------------------------

    messages.append({
        "role":
            "user",

        "content":
            user_question,
    })

    # ========================================================
    # STORE ALL TOOL RESULTS
    # ========================================================

    all_tool_results = []

    # ========================================================
    # TOOL CALLING LOOP
    # ========================================================

    MAX_TOOL_ROUNDS = 5

    for round_number in range(
        MAX_TOOL_ROUNDS
    ):

        # ----------------------------------------------------
        # GROQ TOOL SELECTION
        # ----------------------------------------------------

        try:

            response = (
                await groq
                .chat
                .completions
                .create(

                    model=
                        "openai/gpt-oss-120b",

                    messages=
                        messages,

                    tools=
                        tools,

                    tool_choice=
                        "auto",
                )
            )

        except Exception as error:

            print(
                "Groq tool selection error:",
                error
            )

            raise

        # ----------------------------------------------------
        # ASSISTANT MESSAGE
        # ----------------------------------------------------

        assistant_message = (
            response
            .choices[0]
            .message
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Do NOT use:
        #
        # assistant_message.model_dump()
        #
        # because unsupported fields such as annotations
        # may be included.
        # ----------------------------------------------------

        assistant_dict = (
            build_assistant_message(
                assistant_message
            )
        )

        messages.append(
            assistant_dict
        )

        # ----------------------------------------------------
        # NO MORE TOOL CALLS
        # ----------------------------------------------------

        if not assistant_message.tool_calls:

            break

        # ----------------------------------------------------
        # EXECUTE TOOL CALLS
        # ----------------------------------------------------

        for tool_call in (
            assistant_message.tool_calls
        ):

            tool_name = (
                tool_call
                .function
                .name
            )

            # =================================================
            # PARSE TOOL ARGUMENTS
            # =================================================

            arguments_data = {}

            try:

                arguments_data = json.loads(
                    tool_call
                    .function
                    .arguments
                    or "{}"
                )

            except Exception as error:

                print(
                    "Invalid tool arguments:",
                    error
                )

                messages.append({

                    "role":
                        "tool",

                    "tool_call_id":
                        tool_call.id,

                    "content":
                        json.dumps({
                            "error":
                                "Invalid tool arguments."
                        }),
                })

                continue

            # =================================================
            # CALL MCP TOOL
            # =================================================

            try:

                result = await call_tool(
                    tool_name,
                    arguments_data
                )

            except Exception as error:

                print(
                    f"MCP tool error: {tool_name}",
                    error
                )

                result = {
                    "content": [
                        {
                            "type":
                                "text",

                            "text":
                                json.dumps({
                                    "error":
                                        str(error)
                                }),
                        }
                    ],

                    "isError":
                        True,
                }

            # =================================================
            # STORE TOOL RESULT
            # =================================================

            all_tool_results.append({

                "toolName":
                    tool_name,

                "arguments":
                    arguments_data,

                "result":
                    result,
            })

            # =================================================
            # SEND TOOL RESULT BACK TO GROQ
            # =================================================

            tool_content = (
                extract_tool_content(
                    result
                )
            )

            messages.append({

                "role":
                    "tool",

                "tool_call_id":
                    tool_call.id,

                "content":
                    tool_content,
            })

    # ========================================================
    # CHECK TOOL LOOP
    # ========================================================

    last_message = (
        messages[-1]
    )

    tool_loop_completed = (

        last_message.get(
            "role"
        ) == "assistant"

        and not last_message.get(
            "tool_calls"
        )
    )

    if not tool_loop_completed:

        return {

            "message":
                "Sorry, I could not complete the requested ERP query.",

            "chart":
                None,

            "data":
                all_tool_results,
        }

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    try:

        # ----------------------------------------------------
        # Build ERP data for final model
        # ----------------------------------------------------

        erp_data_text = json.dumps(
            all_tool_results,
            indent=2,
            default=str
        )

        # ----------------------------------------------------
        # Final Groq call
        # ----------------------------------------------------

        final_response = (
            await groq
            .chat
            .completions
            .create(

                model=
                    "openai/gpt-oss-120b",

                messages=[

                    {
                        "role":
                            "system",

                        "content":
                            RESPONSE_SYSTEM_PROMPT,
                    },

                    {
                        "role":
                            "user",

                        "content": f"""
USER QUESTION:

{user_question}


CONVERSATION HISTORY:

{json.dumps(
    history,
    indent=2,
    default=str
)}


ERP TOOL RESULTS:

{erp_data_text}
""",
                    },
                ],

                tool_choice=
                    "none",
            )
        )

    except Exception as error:

        print(
            "Groq final response error:",
            error
        )

        raise

    # ========================================================
    # GET FINAL CONTENT
    # ========================================================

    final_content = (
        final_response
        .choices[0]
        .message
        .content
    )

    # ========================================================
    # PARSE FINAL JSON
    # ========================================================

    parsed_response = (
        parse_final_response(
            final_content
        )
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {

        "message":
            parsed_response[
                "message"
            ],

        "chart":
            parsed_response[
                "chart"
            ],

        "data":
            all_tool_results,
    }