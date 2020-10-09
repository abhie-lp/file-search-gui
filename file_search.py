#!/home/abhishek/Documents/Python/venv/bin/python

import os
import pickle
import PySimpleGUI as sg

from sys import exit
from time import time
from threading import Thread

sg.ChangeLookAndFeel("Reddit")

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(CURR_DIR, "file_indexes")


class GUI:
    def __init__(self):
        self.layout = [
            [
                sg.Text("Search Term", size=(11, 1)),
                sg.Input(size=(45, 1), focus=True, key="TERM",
                         tooltip="File to be searched."),
                sg.Radio("contains", group_id="choice",
                         default=True, key="CONTAINS"),
                sg.Radio("startswith", group_id="choice", key="STARTSWITH"),
                sg.Radio("endswith", group_id="choice", key="ENDSWITH"),
            ],
            [
                sg.Text("Root Path", size=(11, 1),
                        tooltip="Folder to search for the documents."),
                sg.Input(size=(45, 1), key="PATH",
                         default_text=os.path.expanduser("~"),
                         tooltip="Folder to be searched."),
                sg.FolderBrowse("Browse", key="-FOLDER-",
                                initial_folder=os.path.expanduser("~")),
                sg.Button("Search", size=(10, 1),
                          bind_return_key=True, key="-SEARCH-"),
                sg.Button("Clear Indexes", size=(11, 1), key="-CLEAR-",
                          tooltip="Clear all the file indexes created."),
            ],
            [
                sg.Frame(
                    "Ignore folders or extensions",
                    [[sg.Text("Extensions", size=(10, 1),
                              tooltip="Files ending with the given"
                                      " extensions will be ignored. "
                                      "Separate them using ;"),
                      sg.Input(size=(27, 1), key="-EXT-"),
                      sg.Text("Folders", size=(7, 1),
                              tooltip="Folders with given name will "
                                      "be excluded. "
                                      "Separate them using ;"),
                      sg.Input(size=(27, 1), key="-DIR-"),
                      sg.Checkbox("Dot Files/Folders",
                                  default=True, key="-DOT-")]]
                )
            ],
            [
                sg.Text("Open File",
                        tooltip="Click on the icon to open selected file"),
                sg.Button(image_filename=os.path.join(
                    CURR_DIR, "imgs", "file.png"
                ), key="-APP-",
                    image_size=(16, 16),
                    button_color=("LightGray", "LightGray"),
                    tooltip="Open selected file in application."),
                sg.Text("Open in explorer",
                        tooltip="Click on icon to open directory of file.",
                        pad=((20, 0), (0, 0))),
                sg.Button(image_filename=os.path.join(
                    CURR_DIR, "imgs", "folder.png"
                ),
                    image_size=(16, 16), key="-EXPLORER-",
                    button_color=("LightGray", "LightGray"),
                    tooltip="Open selected file in explorer."),
                sg.Text("Bulk Delete",
                        pad=((20, 0), (0, 0)),
                        tooltip="Click on icon to delete selected files."),
                sg.Button(image_filename=os.path.join(
                    CURR_DIR, "imgs", "delete.png"
                ),
                    image_size=(16, 16), key="-DEl-",
                    button_color=("LightGray", "LightGray"),
                    tooltip="Delete selected files."),
            ],
            [
                sg.Listbox(values=[], size=(100, 30), key="-RESULTS-",
                           select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED),
            ],
            [
                sg.Output(size=(100, 12), key="-OUT-")
            ]
        ]
        self.window = sg.Window("File Search Engine",
                                self.layout,
                                finalize=True)
        self.window['-RESULTS-'].bind('<Double-Button-1>', 'dc-')
    
    @staticmethod
    def file_popup(file) -> str:
        """
        Popup to select the action to perform on the double clicked file.
        """
        layout = [
            [sg.Text(f"Select the action to perform on\n\n{file}")],
            [sg.Button("Open File", key="-APP-"),
             sg.Button("Open in File Explorer", key="-EXPLORER-"),
             sg.Button("Delete File", key="-DEl-",
                       button_color=("Black", "OrangeRed"))]
        ]
        window = sg.Window("Open selected file.", layout, finalize=True)
        button, value = window.read()
        window.close()
        del window
        return button


class SearchEngine:
    def __init__(self):
        self.file_index: tuple = ()
        self.modified_time: float = 0
        self.results: list = []
        self.matches: int = 0
        self.records: int = 0
    
    def create_new_index(self, path: str):
        """
        Create new index and save to file
        """
        if path.endswith("/"):
            path = path[:-1]
        self.file_index = ([(root, files)
                            for root, dirs, files in os.walk(path)
                            if files])
        self.modified_time = os.path.getmtime(path)
        
        with open(os.path.join(
                INDEX_DIR, path.replace("/", "_") + ".pkl"
        ), "wb") as f:
            pickle.dump((self.file_index, self.modified_time), f)
    
    def load_existing_index(self, path: str) -> bool:
        """
        Load existing index. If present return True otherwise False
        """
        if path.endswith("/"):
            path = path[:-1]
        try:
            with open(os.path.join(
                    INDEX_DIR, path.replace("/", "_") + ".pkl"
            ), "rb") as f:
                self.file_index, self.modified_time = pickle.load(f)
        except FileNotFoundError:
            self.file_index, self.modified_time = [], 0
            return False
        return True
    
    @staticmethod
    def contains(file, term): return term in file
    
    @staticmethod
    def startswith(file, term): return file.startswith(term)
    
    @staticmethod
    def endswith(file, term): return file.endswith(term)
    
    def search(self, values: dict):
        """
        Search term based on search type
        """
        self.results.clear()
        self.matches, self.records = 0, 0
        # Extensions to be ignored.
        if values["-EXT-"].endswith(";"):
            values["-EXT-"] = values["-EXT-"][:-1]
        if values["-DIR-"].endswith(";"):
            values["-DIR-"] = values["-DIR-"][:-1]
        ignore_extensions = tuple(values["-EXT-"].split(";")) \
            if values["-EXT-"] else ()
        # Folders to be ignored.
        ignore_folders = tuple("/" + folder + "/"
                               for folder in values["-DIR-"].split(";")
                               if values["-DIR-"])
        
        # Check whether to ignore or search dot files/folders
        if values["-DOT-"]:
            ignore_folders = ("/.",) + ignore_folders
        
        if values["CONTAINS"]:
            function = self.contains
        elif values["STARTSWITH"]:
            function = self.startswith
        else:
            function = self.endswith
        
        search_term = values["TERM"].lower()
        for path, files in self.file_index:
            if any(ignored_folder in path + "/"
                   for ignored_folder in ignore_folders):
                continue
            for file in files:
                if file.endswith(ignore_extensions) or \
                        values["-DOT-"] and file.startswith("."):
                    continue
                self.records += 1
                if function(file.lower(), search_term):
                    result = os.path.join(path, file)
                    self.results.append(result)
                    self.matches += 1
        
        with open("search_results.txt", "w") as f:
            f.writelines(self.results)
    
    @staticmethod
    def clear_indexes():
        os.system(f"rm {os.path.join(INDEX_DIR, '*')}")


def notify():
    """
    Send a notification with sound.
    """
    os.system("notify-send 'Search is complete.'")
    os.system("paplay /usr/share/sounds/freedesktop/stereo/complete.oga")


def main():
    """
    Main loop to start the application.
    """
    gui = GUI()
    engine = SearchEngine()
    
    while True:
        event, values = gui.window.Read()
        if event is sg.WIN_CLOSED:
            break
        
        if event == "-SEARCH-":
            search_time = time()
            print(">> Loading file index.")
            if engine.load_existing_index(values["PATH"]):
                # Check whether the modified time of directory matches the
                # indexed modified time. If not then ask to create to a new
                # file index.
                if engine.modified_time != os.path.getmtime(values["PATH"]):
                    confirm = sg.popup_ok_cancel(
                        "The folder appears to be modified. "
                        "Create new index before searching??"
                    )
                    if confirm == "OK":
                        recreate_time = time()
                        engine.create_new_index(values["PATH"])
                        print(">> New file index created. "
                              "[{:.3f}s]".format(time() - recreate_time))
            else:
                print(">> File index not present. Creating new file index")
                index_time = time()
                try:
                    engine.create_new_index(values["PATH"])
                except FileNotFoundError:
                    print(">> Enter a valid directory")
                    continue
                else:
                    print(">> New file index created. "
                          "[{:.3f}]".format(time() - index_time))
            engine.search(values)
            print(">> Searched {} records. "
                  "[{:.3f}s]".format(engine.records, time() - search_time))
            gui.window["-RESULTS-"].Update(values=engine.results)
            Thread(target=notify).start()
            print(">> Files found {}".format(len(engine.results)))
            
            # Set the FolderBrowser location to the current location.
            gui.window.FindElement("-FOLDER-").InitialFolder = values["PATH"]
        elif event == "-CLEAR-":
            clear_time = time()
            engine.clear_indexes()
            print(">> Cleared all file indexes. "
                  "[{:.3f}]".format(time() - clear_time))
        elif event == "-RESULTS-dc-":
            try:
                file, verb, target = values["-RESULTS-"][0], "Opening", "file"
            except IndexError:
                continue
            
            action = gui.file_popup(file)
            if not action:
                continue
            
            command = "xdg-open"
            if action == "-EXPLORER-":
                file = file.rsplit("/", 1)[0]
                target = "folder"
            elif action == "-DEl-":
                command = "rm -f"
                verb = "Deleting"
                engine.results.remove(file)
            print(f">> {verb} {target} for {file}.")
            Thread(target=os.system,
                   args=(f"{command} '{file}'",)).start()
            if action == "-DEl-":
                gui.window["-RESULTS-"].Update(values=engine.results)
                new_index_time = time()
                engine.create_new_index(values["PATH"])
                print(">> New file index created for directory. "
                      f"[{time() - new_index_time:.3f}s]")
        elif event in ("-APP-", "-EXPLORER-"):
            if not values["-RESULTS-"]:
                continue
            file = values["-RESULTS-"][0]
            target = "file"
            if event == "-EXPLORER-":
                file, target = file.rsplit("/", 1)[0], "folder"
            print(f">> Opening {target} for {file}.")
            Thread(target=os.system, args=(f"xdg-open '{file}'",)).start()
        elif event == "-DEl-":
            if not values["-RESULTS-"]:
                continue
            confirm = sg.popup_yes_no("Are u sure to delete "
                                      f"{len(values['-RESULTS-'])} files???")
            if not confirm == "Yes":
                continue
            del_time = time()
            for file in values["-RESULTS-"]:
                os.remove(file)
                print(f">> Deleted {file}.")
            engine.results = [file for file in engine.results
                              if file not in values["-RESULTS-"]]
            gui.window["-RESULTS-"].Update(values=engine.results)
            print(f">> Deleted {len(values['-RESULTS-'])} files. "
                  f"[{time() - del_time:.3f}s]")
            new_index_time = time()
            engine.create_new_index(values["PATH"])
            print(">> New file index created for directory. "
                  f"[{time() - new_index_time:.3f}s]")
        print("*" * 100)
    
    gui.window.close(), exit()
    

if __name__ == "__main__":
    file_index_dir = os.path.join(CURR_DIR, "file_indexes")
    if not os.path.exists(file_index_dir):
        os.mkdir(file_index_dir)
    main()
