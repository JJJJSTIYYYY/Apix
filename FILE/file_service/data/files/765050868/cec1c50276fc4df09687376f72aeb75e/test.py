from typing import Generator

test_data = [1, 2, [3, 4, [5, [6], 7], 8, 9], 0]

def to_plain(data: list) -> list | Generator:
    if isinstance(data, list):
        for item in data:
            yield from to_plain(item)
    else:
        yield data
    return

for item in to_plain(test_data):
    print(item)

print('-----------------------')

loop_times = [0, 0, 0, 0]
context = {
    'loop_times': loop_times
}
deepth = -1

def construct_cases_list():
    sub_item_0 = {
        'mark': 'case',
        'condition': None,
        'value': 1
    }

    sub_item_1 = {
        'mark': 'case',
        'condition': None,
        'value': 2
    }

    sub_item_2_0 = {
        'mark': 'case',
        'condition': None,
        'value': 3
    }

    sub_item_2_1 = {
        'mark': 'case',
        'condition': None,
        'value': 4
    }

    sub_item_2_2_0 = {
        'mark': 'case',
        'condition': None,
        'value': 5
    }

    sub_item_2_2_1_0 = {
        'mark': 'case',
        'condition': None,
        'value': 6
    }

    sub_item_2_2_1 = {
        'mark': 'loop',
        'condition': 'loop_times[3] < 3',
        'content': [
            sub_item_2_2_1_0
        ]
    }

    sub_item_2_2_2 = {
        'mark': 'case',
        'condition': None,
        'value': 7
    }

    sub_item_2_2 = {
        'mark': 'loop',
        'condition': 'loop_times[2] < 3',
        'content': [
            sub_item_2_2_0,
            sub_item_2_2_1,
            sub_item_2_2_2
        ]
    }

    sub_item_2_3 = {
        'mark': 'case',
        'condition': None,
        'value': 8
    }

    sub_item_2_4 = {
        'mark': 'case',
        'condition': None,
        'value': 9
    }

    sub_item_2 = {
        'mark': 'loop',
        'condition': 'loop_times[1] < 3',
        'content': [
            sub_item_2_0,
            sub_item_2_1,
            sub_item_2_2,
            sub_item_2_3,
            sub_item_2_4
        ]
    }

    sub_item_3 = {
        'mark': 'case',
        'condition': None,
        'value': 0
    }

    items = [{
        'mark': 'loop',
        'condition': 'loop_times[0] < 1',
        'content': [
            sub_item_0,
            sub_item_1,
            sub_item_2,
            sub_item_3
        ]
    }]

    print(items)
    return items

def eval_condition(condition_str):
    """Use variable in context"""
    return eval(condition_str, {}, context)

def run_case(case: dict) -> None:
    print(case['value'])

def translate(data: list) -> list | Generator:
    global deepth
    current_deepth = deepth  # 保存进入函数时的深度
    deepth = deepth + 1  # 增加深度计数器
    for item in data:
        if item.get('mark') == 'loop':
            # 初始化当前深度的循环次数
            while len(context.get('loop_times')) <= deepth:
                context.get('loop_times').append(0)
            
            while eval_condition(item.get('condition')):
                yield from translate(item.get('content'))
                # 增加当前深度的循环次数
                context.get('loop_times')[deepth] += 1
#                print(f"Now loop_times is {context.get('loop_times')}")
                # 重置更深层的循环次数
                for i in range(deepth + 1, len(context.get('loop_times'))):
                    context.get('loop_times')[i] = 0
        else:
            yield item
    if deepth < len(context.get('loop_times')):
        context.get('loop_times')[deepth] = 0
    # 恢复深度计数器
    deepth = current_deepth
    return

def run() -> None:
    for item in translate(construct_cases_list()):
        run_case(item)

def main():
    run()

if __name__ == '__main__':
    main()



