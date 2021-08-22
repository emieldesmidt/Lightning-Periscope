class LogColors:
    OKBLUE = '\033[34m'
    OKGREEN = '\033[32m'
    INFORM = '\033[33m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class Logger:

    def __init__(self, owner: str):
        self.owner = owner
        self.length = 50

    def log_error(self, message):
        print(f'{f"{LogColors.FAIL}[{self.owner}]": <46}   {message}{LogColors.ENDC}')

    def log_inform(self, message):
        print(f'{f"{LogColors.INFORM}[{self.owner}]{LogColors.ENDC}": <50}   {message}')

    def log_receive(self, source, message):
        print(f'{f"{LogColors.OKGREEN}[{source} → {self.owner}]{LogColors.ENDC}": <50}   {message}')

    def log_send(self, dest, message):
        print(f'{f"{LogColors.OKBLUE}[{self.owner} → {dest}]{LogColors.ENDC}": <50}   {message}')
