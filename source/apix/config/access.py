from uuid import uuid4


ACCESS_PASSWORD = uuid4().hex


def get_access_password():
    return ACCESS_PASSWORD

def refresh_access_password():
    global ACCESS_PASSWORD
    ACCESS_PASSWORD = uuid4().hex
    return ACCESS_PASSWORD

def check_access_password(pwd: str) -> bool:
    return pwd == ACCESS_PASSWORD