from utilities.files import replace_filenames_with_content
from utilities.ask_answer import Answer
from utilities.workflow import Workflow
from worker.tasks import task


@task
def template_compose(
    workflow_data: dict,
    node_id: str,
):
    """
    Compose template with input fields. If any input field or template is a list, the template will be composed multiple times.
    If there are multiple input fields are list, they must have the same length.

    For example, if input fields are:
    {
        "template": ["{{a}} {{b}}", "{{a}} {{b}}"],
        "a": ["a1", "a2"],
        "b": ["b1", "b2"]
    }
    The output will be:
    ["a1 b1", "a2 b2"]

    If input fields are:
    {
        "template": "{{a}} {{b}}",
        "a": ["a1", "a2"],
        "b": "b",
    }
    The output will be:
    ["a1 b", "a2 b"]

    Args:
        workflow_data (dict): _description_
        node_id (str): _description_

    Raises:
        ValueError: _description_

    Returns:
        _type_: _description_
    """
    workflow = Workflow(workflow_data)
    template = workflow.get_node_field_value(node_id, "模板")
    fields = workflow.get_node_fields(node_id)

    # Check if input fields has list
    fields_has_list = False
    list_length = 1
    for field in fields:
        if field == "输出":
            continue
        field_value = workflow.get_node_field_value(node_id, field)
        if field_value == "BranchSkip":
            workflow.update_node_field_value(node_id, "输出", "BranchSkip")
            return workflow.data
        if not isinstance(field_value, list):
            continue
        fields_has_list = True
        if list_length == 1:
            list_length = len(field_value)
        elif list_length != len(field_value):
            raise ValueError("Input fields have different list length")

    # Build a dict of filed values
    fields_values: dict[str, list] = {"output": []}
    for field in fields:
        if field == "输出":
            continue
        field_value = workflow.get_node_field_value(node_id, field)
        if not isinstance(field_value, list):
            fields_values[field] = [field_value] * list_length
        else:
            fields_values[field] = field_value

    # Compose template
    for index, template in enumerate(fields_values["模板"]):
        for field in fields:
            if field == "输出":
                continue
            template = template.replace(f"{{{{{field}}}}}", str(fields_values[field][index]))
            template = replace_filenames_with_content(template)
        fields_values["output"].append(template)

    if not fields_has_list:
        fields_values["模板"] = fields_values["模板"][0]
    workflow.update_node_field_value(node_id, "模板", fields_values["模板"])

    if not fields_has_list:
        fields_values["output"] = fields_values["output"][0]
    workflow.update_node_field_value(node_id, "输出", fields_values["output"])
    if (workflow.nodesout.get(node_id) == False):
        if workflow_data["answered"]:
            Answer("\n", workflow_data["wid"], workflow_data["streamrunid"])
        else:
            workflow_data["answered"] = True
        Answer(fields_values["output"], workflow_data["wid"], workflow_data["streamrunid"])
    return workflow.data





