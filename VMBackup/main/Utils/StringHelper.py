import datetime

class StringHelper:

    def format_params(self,msg_body, start_delimiter, end_delimiter, *name_value_args):
        if name_value_args:
            for i in range(0, len(name_value_args) - 1, 2):
                msg_body += f"{start_delimiter}{name_value_args[i]} = {name_value_args[i + 1]}{end_delimiter}"
    
    def resolve_string(self,severity_level, message, *args):
        msg_body = datetime.datetime.utcnow().isoformat() + "\t" + "[" + severity_level + "]:\t"

        if message and message.strip():
            msg_body += message + " "

        if args:
            self.format_params(msg_body, "{", "}", *args)

        msg_body += "\n"
        return msg_body

    