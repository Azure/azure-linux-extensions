import datetime

class StringHelper:
    
    def resolve_string(self,severity_level, message):
        msg_body = datetime.datetime.utcnow().isoformat() + "\t" + "[" + severity_level + "]:\t"

        if message and message.strip():
            msg_body += message + " "

        msg_body += "\n"
        return msg_body

    
