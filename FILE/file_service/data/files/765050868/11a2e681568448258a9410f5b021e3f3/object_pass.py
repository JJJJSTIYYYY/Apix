class sub_1:
    def __init__(self, parm: dict):
        self.dict = parm
        
    def append(self, kv: dict):
        self.dict.update(kv)
        
    def print(self):
        print(f"sub_1.dict = {self.dict}")
  

class sub_2:
    def __init__(self, parm: dict):
        self.dict = parm
        
    def append(self, kv: dict):
        self.dict.update(kv)
        
    def print(self):
        print(f"sub_2.dict = {self.dict}")


class top:
    def __init__(self):
        self.dict = {"var1": "val1"}
        self.s1 = sub_1(self.dict)
        self.s2 = sub_2(self.dict)
        
    def append(self, kv: dict):
        self.dict.update(kv)
        
    def print(self):
        print(f"top.dict = {self.dict}")
        
    def print_sub(self):
        print(f"top.s1.dict = {self.s1.dict}")
        print(f"top.s2.dict = {self.s2.dict}")
    

top_obj = top()
top_obj.print()
top_obj.print_sub()
print("----------")
top_obj.s1.append({"var2": "val2"})
top_obj.print()
top_obj.print_sub()
