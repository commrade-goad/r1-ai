import datetime

def chat_helper(supabase, user, query, hist_id):
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
            # TODO: create a new chat and call the ai stuff.
            return {"code": 200, "data": response}
        except Exception as e:
            return {"code": 500, "data": str(e)}
    else:
        # TODO: Finish this
        pass
