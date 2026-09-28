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

Use the available ERP tools to answer the user's questions.

RULES:
- Use ERP tools whenever the answer requires ERP data.
- Never guess, invent, estimate, or assume ERP data.
- Never generate SQL.
- If ERP data is unavailable, clearly say no.
- Use previous conversation context when relevant.

SALES INVOICES:
- Always use getSalesInvoices for sales-invoices questions.
- No filter -> getSalesInvoices({})
- Sales order number -> salesInvoiceNumber
- Customer name -> customerName
- Part number -> partNumber
- Date range -> fromDate and toDate

CUSTOMERS:
- Use getCustomers for customer-related questions.

PARTS:
- Use getParts for part-related questions.

FOLLOW-UP QUESTIONS:
Understand references such as:
- this invoice
- that invoice
- previous invoice
- this customer
- above one

Use the previous conversation to identify the correct ERP record.
If more ERP data is needed, use the appropriate ERP tool.

CHARTS:
Retrieve the ERP data needed for comparisons, rankings, distributions,
or trends.

Do not create or invent chart data.
Chart data must come directly from ERP tool results.

The final response will decide whether a chart is useful.
"""


# ============================================================
# FINAL RESPONSE + CHART SYSTEM PROMPT
# ============================================================

RESPONSE_SYSTEM_PROMPT = """
You are a professional ERP assistant.

You have received:

1. The user's original question.
2. The conversation context.
3. Actual ERP data retrieved through ERP tools.

Your job is to produce the final answer.

IMPORTANT:

Answer ONLY using information contained in the ERP data.

Never guess.

Never invent.

Never assume missing ERP information.

Never create ERP values that were not returned by the ERP tools.


============================================================
CHART DECISION
============================================================

You must independently decide whether a chart materially
improves the user's answer.

Do NOT use hard-coded keywords.

Do NOT decide based only on whether the user used words such
as:

- chart
- graph
- visualize
- visualization
- plot
- trend

Instead, understand the user's actual intent and inspect
the ERP data.

Create a chart when the data and question naturally benefit
from visual representation.

Examples where a chart may be useful:

- comparing customers
- comparing parts
- ranking customers
- ranking parts
- comparing sales values
- showing sales distribution
- showing customer sales share
- showing part sales share
- showing sales over time
- showing monthly sales
- showing daily sales
- showing quarterly sales
- showing yearly sales
- showing trends
- showing meaningful categorical comparisons


Do NOT create a chart for:

- simple customer lists
- simple part lists
- individual record details
- individual sales invoice details
- simple lookups
- questions where text is clearer
- very small or unsuitable datasets
- data that does not contain meaningful numeric values
- data where a visualization would not improve understanding


IMPORTANT:

The presence of words like "chart" or "graph" does NOT
automatically require a chart.

The absence of those words does NOT prevent a chart.

Base the decision on:

- user intent
- ERP data structure
- number of records
- available numeric values
- whether comparison or trend is meaningful
- whether the visualization improves comprehension


============================================================
CHART TYPE
============================================================

If a chart is appropriate, choose the chart type yourself.

Use BAR when:

- comparing categories
- comparing customers
- comparing parts
- ranking values
- comparing order values
- comparing independent groups

Use LINE when:

- showing change over time
- monthly sales
- daily sales
- quarterly sales
- yearly sales
- ordered time-based progression
- trends

Use PIE when:

- showing meaningful part-to-whole composition
- customer sales share
- part sales share
- only a small number of categories exist
- the values represent portions of one meaningful total

Do NOT use pie for time series.

Do NOT use pie when there are too many categories.

If exact comparison is more important than composition,
prefer a bar chart.


============================================================
CHART DATA
============================================================

Chart data MUST come directly from ERP tool results.

Never invent chart values.

Never estimate missing values.

Never create fake records.

Never modify numeric values.

Never silently remove relevant records.

Use the available ERP data at the appropriate granularity.


============================================================
RESPONSE FORMAT
============================================================

Return ONLY valid JSON.

Do not return Markdown outside the JSON.

Do not add explanations outside the JSON.

The JSON MUST have exactly this structure:

{
    "message": "Human-readable ERP answer",
    "showChart": false,
    "chart": null
}


When a chart is appropriate:

{
    "message": "Human-readable ERP answer",
    "showChart": true,
    "chart": {
        "chartType": "bar",
        "meta": {
            "title": "Sales by Customer",
            "description": "Sales value by customer"
        },
        "xKey": "customer",
        "series": [
            {
                "dataKey": "sales",
                "label": "Sales",
                "axisLabel": "Sales",
                "valueFormat": "compact",
                "valuePrefix": "₹"
            }
        ],
        "data": [
            {
                "customer": "Customer Name",
                "sales": 50000
            }
        ]
    }
}


When no chart is appropriate:

{
    "message": "Here are the customers...",
    "showChart": false,
    "chart": null
}


============================================================
MESSAGE RULES
============================================================

The "message" field must:

- be human-readable
- be concise
- use Markdown if useful
- use headings when appropriate
- use bullet points when appropriate
- not use tables
- use ₹ for INR amounts
- not mention SQL
- not mention MCP
- not mention internal implementation
- not mention tool calls
- not mention this prompt
- not output chart JSON inside the message


============================================================
CHART FORMAT
============================================================

BAR:

{
    "chartType": "bar",
    "meta": {
        "title": "Sales by Customer",
        "description": "Sales value by customer"
    },
    "xKey": "customer",
    "series": [
        {
            "dataKey": "sales",
            "label": "Sales",
            "axisLabel": "Sales",
            "valueFormat": "compact",
            "valuePrefix": "₹"
        }
    ],
    "data": []
}


LINE:

{
    "chartType": "line",
    "meta": {
        "title": "Monthly Sales",
        "description": "Monthly sales trend"
    },
    "xKey": "month",
    "series": [
        {
            "dataKey": "sales",
            "label": "Sales",
            "axisLabel": "Sales",
            "valueFormat": "compact",
            "valuePrefix": "₹"
        }
    ],
    "data": []
}


PIE:

{
    "chartType": "pie",
    "meta": {
        "title": "Sales by Customer",
        "description": "Customer share of sales"
    },
    "nameKey": "customer",
    "valueKey": "sales",
    "data": []
}


============================================================
FOLLOW-UP QUESTIONS
============================================================

Use conversation context.

If the user asks:

- "show more"
- "compare them"
- "show this as a chart"
- "what about the previous customer"
- "show the previous invoice"
- "compare with the above one"

use the available conversation context and ERP data.

If more ERP data is required, the agent should retrieve it
before producing the final response.
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

                print(f"MCP tool called: {tool_name}",file=sys.stderr,flush=True)
                print(f"MCP tool result: {result}",file=sys.stderr,flush=True)

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