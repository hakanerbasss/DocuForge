from app.project.project import DocumentaryProject

project = DocumentaryProject(
    title="Dünya dursa ne olurdu?"
)

folder = project.create()

print(folder)
