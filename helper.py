import datetime
from supabase import Client

def chat_helper(supabase: Client, user, query, hist_id):
    id_to_use = hist_id
    if hist_id is None: # create new hist
        try:
            response = (
                supabase.table("history")
                .insert(
                    {
                        "user_id": user.id,
                        "title": query[:20], # for now just take the first 20 char to be the title.
                        "created_at": datetime.datetime.now()
                    }
                )
                .execute()
            )
            id_to_use = response.data[0].get("id")
        except Exception as e:
            return {"code": 500, "data": str(e)}

    if id_to_use is None:
        return {"code": 401, "data": "Invalid hist id"}

    # TODO: actually call the ai.
    ai_response = ""
    try:
        response = (
            supabase.table("chat")
            .insert(
                {
                    "history_id": id_to_use,
                    "query": query,
                    "response": "WIP",
                    "created_at": datetime.datetime.now(),
                }
            ).execute()
        )
        return {"code": 200, "data": ai_response}
    except Exception as e:
        return {"code": 500, "data": str(e)}
