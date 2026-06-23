import asyncio
import copy
import inspect
from abc import ABC
from typing import Any

from apix_agent.commons.logger import Logger


class ExecutionContextBase(ABC):

    def __init__(self):
        super().__init__()
        self._updates_lock = asyncio.Lock()
        self._updates: dict = {}

        self.context_group: dict[str, list] = {}


    def print_context(self, logger: Logger):
        """
        Print all public context variables.

        Public variables are instance attributes whose names do not start
        with an underscore ("_").

        Args:
            logger (Logger): Logger used to output context information.
        """
        print_line = ["Get following context:"]

        for name, value in vars(self).items():
            if not name.startswith("_"):
                print_line.append(f"{name}: {value}")
        
        logger.info(f"{"\n".join(print_line)}")

    
    def print_method(self, logger: Logger):
        """
        Print all public methods of the current object.

        For each method, the following information will be displayed:
        - Method name
        - Parameter names and type annotations
        - Return type annotation
        - Docstring (if available)

        Methods whose names start with an underscore ("_") are ignored.

        Args:
            logger (Logger): Logger used to output method information.
        """
        print_line = ["Get following methods:"]

        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("_"):
                continue

            signature = inspect.signature(method)

            params = []
            for param_name, param in signature.parameters.items():
                annotation = param.annotation

                if annotation is inspect.Parameter.empty:
                    annotation_str = "Any"
                elif hasattr(annotation, "__name__"):
                    annotation_str = annotation.__name__
                else:
                    annotation_str = str(annotation)

                params.append(f"{param_name}: {annotation_str}")

            return_annotation = signature.return_annotation
            if return_annotation is inspect.Signature.empty:
                return_str = "Any"
            elif hasattr(return_annotation, "__name__"):
                return_str = return_annotation.__name__
            else:
                return_str = str(return_annotation)

            print_line.append(f"{name}({', '.join(params)}) -> {return_str}")

            doc = inspect.getdoc(method)
            if doc:
                print_line.append(doc)
                
        logger.info(f"{"\n".join(print_line)}")


    def register_a_group(
        self,
        group_name: str,
        member: list[str] | None = None,
        exist_ok: bool = False,
    ):
        """
        Register a context group.

        Args:
            group_name (str): Group name to register.
            member (list[str]): A string list of member variable.
            exist_ok (bool): Allow append to exist group.
                If exist_ok is False and group already exists,
                this method will raise RuntimeError.
        """
        member = member or []

        if not exist_ok and group_name in self.context_group:
            raise RuntimeError(f"Group {group_name} already exists.")

        context = self.get_context()

        invalid_members = [
            name
            for name in member
            if name not in context
        ]

        if invalid_members:
            raise RuntimeError(f"Invalid members: {invalid_members}")

        member_list = self.context_group.get(group_name, [])

        for name in member:
            if name not in member_list:
                member_list.append(name)

        self.context_group[group_name] = member_list


    def remove_group(self, group_name: str, missing_ok: bool = True):
        """
        Remove a context group.

        Args:
            group_name (str): Group name to remove.
            missing_ok (bool): Ignore if group does not exist.
        """
        if group_name not in self.context_group:
            if missing_ok:
                return

            raise RuntimeError(f"Group {group_name} does not exist.")

        self.context_group.pop(group_name, None)


    def list_all_group(self) -> dict:
        """
        Return all group.
        """
        return copy.deepcopy(self.context_group)
    

    def get_context(
        self,
        key: str | None = None,
        group: str | None = None,
    ) -> dict[str, Any] | Any:
        """
        Get public context variables.

        Args:
            key (str): Context variable name. If None, return all public
                context variables as a dictionary.
            group (str): Group name.

        Returns:
            If key is None, returns a dictionary mapping variable names
            to values. Otherwise, returns the value of the specified
            variable or None if it does not exist.
        """
        # Get all public attributes
        context = {
            name: value
            for name, value in vars(self).items()
            if not name.startswith("_")
        }

        # No group specified
        if group is None:
            if key is None:
                return context
            return context.get(key)

        # Group specified
        filter_k = self.context_group.get(group)

        if filter_k is None:
            return {} if key is None else None

        if key is not None:
            if key not in filter_k:
                return None
            return context.get(key)

        return {
            k: v
            for k, v in context.items()
            if k in filter_k
        }
    
    
    async def update_context(self, in_group: str = None, **updates):
        """
        Update existing public context variables and record successful updates.

        Only existing public attributes (whose names do not start with "_")
        can be updated. Successful updates will be stored in self._updates.

        If you do not want to keep the updates, use clear_updates()

        Args:
            in_group: Skip update if a key not in target group.
            **updates: Context variables to update.
        """
        async with self._updates_lock:
            context = self.get_context(group=in_group)

            for k, v in updates.items():
                if k not in context:
                    continue

                setattr(self, k, v)
                self._updates[k] = v


    async def get_updates(self) -> dict:
        """
        Get self._updates.

        Returns:
            A dict keeps all update opration.
        """
        async with self._updates_lock:
            return copy.deepcopy(self._updates)
        
        
    async def clear_updates(self):
        """
        Clear the updates.
        """
        async with self._updates_lock:
            self._updates.clear()