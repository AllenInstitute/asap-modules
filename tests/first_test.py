import pytest
import renderapi

args = {
    "host":"localhost",
    "port":"8080",
    "owner":"testowner",
    "project":"testproject",
    "client_scripts":"\var\www\render\render-ws\src\main\scripts"
}
def first_test():
    render = renderapi.connect(**args)
    owners = renderapi.render.get_owners()
    assert(len(owners)==1)
    

    