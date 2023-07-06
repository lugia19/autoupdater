# Go+Python installer/updater

Essentially, this is just an installer designed to pull a project from a specified github repo, and install its prerequisites in a venv.

The components that are required to ship an application using it are:
- The Go executable (exe for windows for example)
- A python venv (located in base-venv). It does not require any packages to be installed.
- The install.py script and base-requirements.txt
- A repo.json file containing the settings (such as the github repository, etc)

The rundown on its functionality is:

- Go program: 
  - Functions as the entrypoint (gets called to actually start the program)
  - Will create a new venv from base-venv if not already done
  - Will call install.py from it
- Install.py: 
  - Will install its own prerequisites (from base-requirements.txt) if missing
  - Will use dulwich to clone/pull the specified github repo
  - Will install the requirements from the repo's requirements.txt (or try to update them if the repo has been updated)
    - It will also first install those from requirements-torch.txt if present. This is designed to allow you to install pytorch with CUDA easily.
  - It will launch the script defined in repo.json to start the application itself