from tools.code_runner.python_code_runner import python_code_runner
from tools.basic_tools.health_cheak import check_health

tool = {
    'CodeRunner': python_code_runner,
    'ServerCheck': check_health,
}