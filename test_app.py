from fastmcp import FastMCPApp
app = FastMCPApp("TestApp")

@app.ui()
def main():
    from prefab_ui.components import Text
    return Text("Hello World")
