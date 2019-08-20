import tkinter as tk
import tkinter.ttk as ttk
import sqlite3 as sql
import requests
import threading
import os
import ast
import csv
import datetime
from PIL import ImageTk, Image
from tkinter.filedialog import askopenfilename
from acrcloud.recognizer import ACRCloudRecognizer
from tkinter import messagebox

# online recognition succeeds or not
def online_success(rlt_dict, cur, site_name, tbLogs):
    rec_title = rlt_dict['metadata']['custom_files'][0]['title']
    rec_duration = str(round(int(rlt_dict['metadata']['custom_files'][0]['duration_ms']) / 1000))

    rec_start_datetime = datetime.datetime.strptime(str(rlt_dict['metadata']['timestamp_utc']), '%Y-%m-%d %H:%M:%S')
    rec_end_datetime = rec_start_datetime + datetime.timedelta(seconds=float(rec_duration))

    # print(rec_title, rec_duration, rec_start_datetime, rec_end_datetime)

    cmd = "SELECT client, artist, album, genre, year, comment FROM song_tb WHERE title == " + "\'" + rec_title + "\'"
    cur.execute(cmd)
    rlt_one_data = cur.fetchone()
    # print(rlt_one_data)

    site_name = str(site_name.get())
    tbLogs.insert('', tk.END, text='Local', values=(
        rec_title, rlt_one_data[0], rec_start_datetime, rec_end_datetime, rlt_one_data[1], rlt_one_data[2], rlt_one_data[3], rlt_one_data[4],
        rlt_one_data[5]))
    return


# this class records radio stream from online site
# distinguishes if it exists in database, or not
class RecProcessingRadio(threading.Thread):

    def __init__(self, name, url, acr_cloud, cur, site_name, tbLogs, status):
        super(RecProcessingRadio, self).__init__()
        self._stop_event = threading.Event()
        self.name = name
        self.url = url
        self.acr_cloud = acr_cloud
        self.cur = cur
        self.site_name = site_name
        self.tbLogs = tbLogs
        self.status = status

    def run(self):
        try:
            stream_socket = requests.get(self.url, stream=True)
        except:
            print('Radio site exception occurred...')
            self.status.config(foreground='black')
            messagebox.showerror("Error", "Radio site is not available!")
            return

        rec_cycle = 0
        global stream_file

        # run until thread event is set.
        while not self.stopped():
            with open('./stream.mp3', 'wb') as stream_file:
                try:
                    for block in stream_socket.iter_content(122880):
                        stream_file.write(block)
                        break
                except:
                    self.status.config(foreground='black')
                    messagebox.showerror("Error", "Radio site is not available!")
                    return

            rec_cycle += 1

            # recognize music by using ACR api
            rlt = self.acr_cloud.recognize_by_file('stream.mp3', 0)

            print('Cycle: ', rec_cycle, ':', rlt)

            rlt_dict = ast.literal_eval(rlt)  # convert string to dictionary
            status = str(rlt_dict['status']['msg'])
            code = rlt_dict['status']['code']

            # if music can't be recognitzed
            if code == 2004:
                self.status.config(foreground='black')
                messagebox.showerror("Error", "Music is not available to recognize!")
                return

            # if recognition succeed
            if status == 'Success':
                online_success(rlt_dict, self.cur, self.site_name, self.tbLogs)

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


# main application
class MainApplication(tk.Frame):

    def __init__(self, config, master=None):
        super().__init__(master)

        self.acr_cloud = re = ACRCloudRecognizer(config)

        self.db = sql.connect('./db.sqlite3')
        self.cur = self.db.cursor()

        w, h = 1000, 550  # size of main window

        # screen size of display
        ws = self.master.winfo_screenwidth()
        hs = self.master.winfo_screenheight()

        # center position
        x = (ws / 2) - (w / 2)
        y = (hs / 2) - (h / 2)

        # configure main window
        self.master.title('Radio Surveillance System')
        self.master.geometry('%dx%d+%d+%d' % (w, h, x, y))
        self.master.resizable(0, 0)

        self.config(background='saddle brown')
        self.pack(fill=tk.BOTH, expand=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # create initial widgets
        self.create_widget()
        return

    def create_widget(self):
        """
        this creates initial widgets and layouts.
        :param event:
        :return: void
        """

        # variable declaration
        self.source_type = tk.IntVar()  # radio value (online / local file)
        self.site_name = tk.StringVar()     # site name
        self.file_path = tk.StringVar()     # local file path

        # top-left frame contains url input box, folder and go button, and url status
        self.frmUrl = tk.Frame(self, background='NavajoWhite3')

        # top-right patch image
        imgPatch = ImageTk.PhotoImage(Image.open('./res/top_right_patch.png'))
        self.lblPatch = tk.Label(self.frmUrl, background='NavajoWhite3', image=imgPatch)
        self.lblPatch.image = imgPatch

        s = ttk.Style(self.frmUrl)  # Creating style element
        s.theme_use('clam')
        s.configure('Wild.TRadiobutton',  # First argument is the name of style. Needs to end with: .TRadiobutton
                    background='NavajoWhite3')  # Setting background to our specified color above
        s.configure('Treeview', background='snow2', fieldbackground="snow2")

        self.radioOnline = ttk.Radiobutton(self.frmUrl, text='Online Radio', variable=self.source_type, value=0,
                                           command=self.click_online, style='Wild.TRadiobutton', width=12,
                                           cursor='hand2')
        self.radioOffline = ttk.Radiobutton(self.frmUrl, text='Local File', variable=self.source_type, value=1,
                                            command=self.click_local_file, style='Wild.TRadiobutton', width=12,
                                            cursor='hand2')

        imgLink = ImageTk.PhotoImage(Image.open('./res/btnLink.png'))
        imgFolder = ImageTk.PhotoImage(Image.open('./res/btnFolder.png'))

        self.imgGo = ImageTk.PhotoImage(Image.open('./res/btnGo.png'))
        self.imgGoOver = ImageTk.PhotoImage(Image.open('./res/btnGo_over.png'))
        self.imgGoDown = ImageTk.PhotoImage(Image.open('./res/btnGo_down.png'))

        self.lblLink = tk.Label(self.frmUrl, image=imgLink, background='NavajoWhite3')
        self.lblLink.image = imgLink

        self.cmbUrl = ttk.Combobox(self.frmUrl, state='readonly', textvariable=self.site_name,
                                   width=50, height=5, font=("Constantia",12,"bold"), cursor='hand2')
        self.cmbUrl.bind('<<ComboboxSelected>>', self.change_site_name)
        self.entUrl = tk.Entry(self.frmUrl, textvariable=self.file_path, width=47, relief=tk.SOLID,
                               font=("Constantia", 13, "bold"), borderwidth=1)

        self.btnFolder = tk.Button(self.frmUrl, image=imgFolder, command=self.open_file_dialog,
                                   state=tk.DISABLED, width=20, height=20, cursor='hand2')
        self.btnFolder.image = imgFolder

        self.lblGo = tk.Label(self.frmUrl, image=self.imgGo, background='NavajoWhite3', cursor='hand2')
        self.lblGo.image = self.imgGo

        self.lblGo.bind('<Enter>', self.go_over)
        self.lblGo.bind('<Leave>', self.go_normal)
        self.lblGo.bind('<Button-1>', self.go_down)
        self.lblGo.bind('<ButtonRelease-1>', self.go_up)

        self.lblStatus = tk.Label(self.frmUrl, background='wheat3')

        self.radioOnline.grid(row=0, column=1, sticky=tk.S+tk.W, pady=5)
        self.radioOffline.grid(row=0, column=2, sticky=tk.S+tk.W, pady=5)
        self.lblLink.grid(row=1, column=0, padx=10)
        self.cmbUrl.grid(row=1, column=1, columnspan=2, sticky=tk.S, pady=5)
        self.btnFolder.grid(row=1, column=3, padx=5, sticky=tk.S, pady=5)
        self.lblGo.grid(row=0, column=4, padx=8, rowspan=2, sticky=tk.S)
        self.lblStatus.grid(row=2, column=0, columnspan=5, sticky=tk.E+tk.W, padx=20)
        self.lblPatch.grid(row=0, column=5, rowspan=3)

        # get radio site names which have valid streaming url
        cmd = "SELECT name, address, link FROM site_tb WHERE link != 'Unknown'"
        self.cur.execute(cmd)
        self.site_list = self.cur.fetchall()
        self.cmbUrl['values'] = sorted([x[0] for x in self.site_list])
        self.cmbUrl.current(0)
        self.lblStatus.configure(text=self.site_list[0][1])
        # end of top-left frame


        # bottom frame shows monitoring logs
        self.frmLogs = tk.Frame(self, width=800, height=300, background='NavajoWhite3')

        imgEarphone = ImageTk.PhotoImage(Image.open('./res/btnEarphone.png'))
        imgMigPatch = ImageTk.PhotoImage(Image.open('./res/mid_patch.png'))

        self.imgCSV = ImageTk.PhotoImage(Image.open('./res/btnCsv.png'))
        self.imgCSVOver = ImageTk.PhotoImage(Image.open('./res/btnCsv_over.png'))

        self.lblEarphone = tk.Label(self.frmLogs, image=imgEarphone, background='NavajoWhite3')
        self.lblEarphone.image = imgEarphone

        self.lblMidPatch = tk.Label(self.frmLogs, background='NavajoWhite3', image=imgMigPatch)
        self.lblMidPatch.image = imgMigPatch

        self.lblCsv = tk.Label(self.frmLogs, image=self.imgCSV, background='NavajoWhite3', borderwidth=1,
                               relief="groove", cursor='hand2')
        self.lblCsv.image = self.imgCSV
        self.lblCsv.bind('<Enter>', self.csv_over)
        self.lblCsv.bind('<Leave>', self.csv_normal)
        self.lblCsv.bind('<Button-1>', self.csv_down)
        self.lblCsv.bind('<ButtonRelease-1>', self.csv_up)

        headers = ('title', 'client', 'start_time', 'end_time', 'artist', 'album', 'genre', 'year', 'comment')
        header_titles = ['Site Name', 'Title', 'Client', 'Start Time', 'End Time', 'Artist', 'Album', 'Genre', 'Year', 'Comment']
        column_sizes = [140, 190, 120, 120, 120, 90, 90, 80, 70, 220]

        self.tbLogs = ttk.Treeview(self.frmLogs, column=headers, selectmode='browse')

        for i in range(len(header_titles)):
            self.tbLogs.heading('#' + str(i), text=header_titles[i], anchor=tk.W)
            self.tbLogs.column('#' + str(i), width=column_sizes[i])

        xsb = ttk.Scrollbar(self.frmLogs, orient=tk.HORIZONTAL, command=self.tbLogs.xview)
        ysb = ttk.Scrollbar(self.frmLogs, orient=tk.VERTICAL, command=self.tbLogs.yview)

        self.tbLogs.configure(xscrollcommand=xsb.set)
        self.tbLogs.configure(yscrollcommand=ysb.set)

        self.lblEarphone.grid(row=0, column=0, sticky=tk.W, padx=15)
        self.lblCsv.grid(row=0, column=2)
        self.tbLogs.grid(row=1, column=0, columnspan=3, sticky=tk.W + tk.E + tk.N + tk.S)
        xsb.grid(row=2, column=0, columnspan=3, sticky=tk.E + tk.W)
        ysb.grid(row=1, column=3, rowspan=2, sticky=tk.N + tk.S)
        self.lblMidPatch.grid(row=0, column=1)
        # end of bottom frame


        # frame layout
        self.frmUrl.grid(row=0, column=0, sticky=tk.W + tk.E + tk.N + tk.S, pady=10)
        self.frmLogs.grid(row=1, column=0, sticky=tk.W + tk.E + tk.N + tk.S)

        # this indicates increase the column of table (index = 0, weight = 1)
        self.frmLogs.grid_columnconfigure(0, weight=1)
        self.frmLogs.grid_rowconfigure(1, weight=1)

        cmd = "SELECT * FROM log_tb"
        self.cur.execute(cmd)
        rlt_all_data = self.cur.fetchall()

        for item in rlt_all_data:
            self.tbLogs.insert('', tk.END, text=item[1], values=(
                item[2], item[3], item[4], item[5], item[6],
                item[7], item[8], item[9], item[10]))
        # print(rlt_all_data)
        return

    ######################################
    #     "Go" button event handlers     #
    ######################################
    def go_normal(self, event):
        self.lblGo.config(image=self.imgGo)
        self.lblGo.image = self.imgGo
        return

    def go_over(self, event):
        self.lblGo.config(image=self.imgGoOver)
        self.lblGo.image = self.imgGoOver
        return

    def go_down(self, event):
        self.lblGo.config(image=self.imgGoDown)
        self.lblGo.image = self.imgGoDown
        self.lblStatus.config(foreground='red2')
        return

    def go_up(self, event):
        self.lblGo.config(image=self.imgGoOver)
        self.lblGo.image = self.imgGoOver

        if self.source_type.get() == 0:     # in the case of online radio recognition
            # stream_url = 'http://s2.voscast.com:9304/;'
            stream_url = ''
            for item in self.site_list:
                if self.site_name.get() == item[0]:
                    stream_url = item[2]        # get original streaming site address of radio site
                    break

            print(stream_url)

            global processing
            processing = RecProcessingRadio(name='monitoring', url=stream_url, acr_cloud=self.acr_cloud,
                                            cur=self.cur, site_name=self.site_name, tbLogs=self.tbLogs, status=self.lblStatus)
            processing.setDaemon(True)  # close this thread when main thread exits
            processing.start()
        elif self.source_type.get() == 1:   # in the case of local file recognition
            try:
                rlt = self.acr_cloud.recognize_by_file(self.fname, 0)
                # print(type(rlt), rlt)

                rlt_dict = ast.literal_eval(rlt)  # convert string to dictionary
                status = str(rlt_dict['status']['msg'])

                if status == 'Success':
                    self.on_success(rlt_dict)
                else:
                    self.lblStatus.config(foreground='black')
            except:
                print('Undefined fila name...')

        return

    ######################################
    #     "CSV" button event handlers    #
    ######################################
    def csv_normal(self, event):
        self.lblCsv.config(image=self.imgCSV)
        self.lblCsv.image = self.imgCSV
        return

    def csv_over(self, event):
        self.lblCsv.config(image=self.imgCSVOver)
        self.lblCsv.image = self.imgCSVOver
        return

    def csv_down(self, event):
        self.lblCsv.config(image=self.imgCSV)
        self.lblCsv.image = self.imgCSV
        return

    def csv_up(self, event):
        self.lblCsv.config(image=self.imgCSVOver)
        self.lblCsv.image = self.imgCSVOver

        childrens = self.tbLogs.get_children()
        item_count = len(childrens)
        # print(item_count)

        file_name = "output_{}.csv".format(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
        with open(file_name, 'w', newline='') as resultFile:
            wr = csv.writer(resultFile, dialect='excel')

            csv_data = [
                ['Site Name', 'Title', 'Client', 'Start Time', 'End Time', 'Artist', 'Album', 'Genre', 'Year', 'Comment']
            ]
            for i in range(item_count):
                tp = self.tbLogs.item(childrens[i])['values']
                tp1 = self.tbLogs.item(childrens[i])['text']
                tp.insert(0, tp1)
                csv_data.append(tp)

            if len(csv_data) == 1:
                messagebox.showerror("Error", "No data to export!")
                return

            # print(csv_data)
            wr.writerows(csv_data)

        self.tbLogs.delete(*self.tbLogs.get_children())
        messagebox.showinfo("Success", "All data was exported successfully")
        return

    # change site url
    def change_site_name(self, event):
        try:
            self.lblStatus.config(foreground='black')
            processing.stop()   # stop previous thread
        except:
            pass

        # show radio site address in status bar
        for item in self.site_list:
            if self.site_name.get() == item[0]:
                self.lblStatus.configure(text=item[1])
                break
        return

    # option of online radio stream
    def click_online(self):
        self.source_type.set(0)     # set textvariable as online recognition
        self.entUrl.grid_forget()       # hide local file input box
        self.cmbUrl.grid(row=1, column=1, columnspan=2, sticky=tk.S, pady=5)       # show online site combobox
        self.btnFolder.configure(state=tk.DISABLED)     # disable folder button for local file browser

        # change status bar
        for item in self.site_list:
            if self.site_name.get() == item[0]:
                self.lblStatus.configure(text=item[1])
                break
        return

    # option of local file
    def click_local_file(self):
        self.source_type.set(1)     # set textvariable as local recognition

        try:
            self.lblStatus.config(foreground='black')
            processing.stop()       # close online recognition thread
        except:
            pass

        self.cmbUrl.grid_forget()       # hide online site combobox
        self.entUrl.grid(row=1, column=1, columnspan=2, sticky=tk.S, pady=5)       # show local file input box
        self.btnFolder.configure(state=tk.NORMAL)   # make the folder button normal

        # change status bar
        self.lblStatus.configure(text=self.file_path.get())
        return

    # open file dialog
    def open_file_dialog(self):
        # get file name from open file dialog
        self.fname = askopenfilename(filetypes=(("MP3 File", "*.mp3"),
                                           ("wav", "*.wav"),))
        if self.fname:
            try:
                self.file_path.set(self.fname)
                self.lblStatus.configure(text=self.fname)
            except:  # naked except is a bad idea
                print("Open Source File", "Failed to read file\n'%s'" % self.fname)
            return
        return

    # in the case of successfully recognized of local file
    def on_success(self, rlt_dict):
        rec_title = rlt_dict['metadata']['custom_files'][0]['title']
        rec_duration = str(round(int(rlt_dict['metadata']['custom_files'][0]['duration_ms']) / 1000))

        rec_start_datetime = datetime.datetime.strptime(str(rlt_dict['metadata']['timestamp_utc']), '%Y-%m-%d %H:%M:%S')
        rec_end_datetime = rec_start_datetime + datetime.timedelta(seconds=float(rec_duration))

        # print(rec_title, rec_duration, rec_start_datetime, rec_end_datetime)

        music_name = str(self.fname).split('/')[-1]
        cmd = "SELECT client, artist, album, genre, year, comment FROM song_tb WHERE title == " + "\'" + music_name + "\'"
        self.cur.execute(cmd)
        rlt_one_data = self.cur.fetchone()
        # print(rlt_one_data)

        site_name = str(self.site_name.get())
        self.tbLogs.insert('', tk.END, text='Local', values=(
        rec_title, rlt_one_data[0], rec_start_datetime, rec_end_datetime, rlt_one_data[1],
        rlt_one_data[2], rlt_one_data[3], rlt_one_data[4], rlt_one_data[5]))

        self.lblStatus.config(foreground='black')
        return

    # when click close button
    def on_closing(self):
        if messagebox.askokcancel("Quit", "You didn't export data to CSV file.\n\nDo you want to store all data in database."):
            childrens = self.tbLogs.get_children()
            item_count = len(childrens)
            # print(item_count)

            self.cur.execute('DELETE FROM log_tb')
            self.db.commit()

            for i in range(item_count):
                tp = self.tbLogs.item(childrens[i])['values']
                tp1 = self.tbLogs.item(childrens[i])['text']

                cmd = "INSERT INTO log_tb (site_name, title, client, start_time, end_time, artist, album, genre, year, comment) " \
                      "VALUES ('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}')" \
                        .format(tp1, tp[0], tp[1], tp[2], tp[3], tp[4], tp[5], tp[6], tp[7], tp[8])
                self.cur.execute(cmd)
                self.db.commit()

            self.master.destroy()
        return


def main():
    # configuration for ACR cloud service
    config = {
        # Replace "xxxxxxxx" below with your project's host, access_key and access_secret.
        'host': 'identify-us-west-2.acrcloud.com',
        'access_key': 'ff3451e6e3f5a78ff022f36966e9147a',
        'access_secret': 'oySb1OAzH2JZ9UFgKZy9nFWPfZ0FBqcX1PNvqEgZ',
        'timeout': 10  # seconds
    }

    root = tk.Tk()
    app = MainApplication(config, root)
    app.mainloop()

    try:
        app.db.close()      # close db
        stream_file.close()       # close stream file
        os.remove('./stream.mp3')   # delete stream file
    except:
        pass

    print("Exit App...")


if __name__ == '__main__':
    main()
