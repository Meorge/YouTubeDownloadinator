from __future__ import unicode_literals
import youtube_dl
import re
import threading

from PyQt5 import QtWidgets, QtGui, QtCore
import sys
from datetime import timedelta

from typing import List

import os.path
from mutagen.id3 import ID3, TPE1, TPE2, TIT2, TRCK, TALB, APIC, TYER, TCON, TRCK


"""
TODO:
 - Add function to TrackItem to download the song
 - After song is downloaded, it should apply metadata
 - File selector for thumbnail?

"""


url = "https://www.youtube.com/playlist?list=PLtPXiJedNjDFfsaMKnhsJyOZH823bXzMt"

download_metadata_options = {
    'writesubtitles': True,
    'format': 'mp4',
    'writethumbnail': True,
    'sleep_interval': 0,
    'max_sleep_interval': 0,
    'skip_download': True,
    'simulate': True
}

def get_names_in_playlist(url):
    try:
        with youtube_dl.YoutubeDL(download_metadata_options) as ydl:
            ie_result = ydl.extract_info(url, False)
            if "_type" in ie_result: # it's a playlist
                return ie_result["entries"]
            else: # it's a single video
                return ie_result
    except Exception as e:
        print(e)
        return []

class TrackItem(QtCore.QObject):
    def __init__(self, parent, trackData={"title": "TITLE", "duration": 0}, trackIndex = (0,0)):
        super(TrackItem, self).__init__(parent)
        self.__rawName = trackData["title"]
        self.__trackTitle = trackData["title"]
        self.__trackArtist = "ARTIST"
        self.__trackAlbum = "ALBUM"
        self.__trackAlbumArtPath = ""
        self.__trackYear = "YEAR"
        self.__trackGenre = "Soundtrack"
        self.__duration = trackData["duration"]

        self.__url = trackData["webpage_url"]

        self.__trackIndex = trackIndex

        self.__progressBar: ProgressIndicator = None
        self.__downloadThread = None

    def title(self):
        return self.__trackTitle

    def artist(self):
        return self.__trackArtist

    def album(self):
        return self.__trackAlbum

    def year(self):
        return self.__trackYear

    def albumArtPath(self):
        return self.__albumArtPath

    def genre(self):
        return self.__trackGenre

    def rawName(self):
        return self.__rawName

    def duration(self):
        return self.__duration

    def readableDuration(self):
        return timedelta(seconds=self.duration())

    def trackIndex(self):
        return self.__trackIndex

    def url(self):
        return self.__url

    def setTitle(self, title):
        self.__trackTitle = title

    def setArtist(self, artist):
        self.__trackArtist = artist

    def setAlbum(self, album):
        self.__trackAlbum = album

    def setYear(self, year):
        self.__trackYear = year

    def setAlbumArtPath(self, path):
        self.__albumArtPath = path

    def setGenre(self, genre):
        self.__trackGenre = genre

    def progressBar(self):
        return self.__progressBar

    def setProgressBar(self, bar):
        self.__progressBar = bar

    def applyRegexTitlePattern(self, pattern):
        regexMatches = re.match(pattern, self.rawName())
        if regexMatches is None:
            print("no matches I guess??")
        elif len(regexMatches.groups()) == 0:
            print("Not enough groups!")
        else:
            self.setTitle(regexMatches.group(1))


    def updateProgress(self, d):
        if d["status"] == "downloading":
            downloaded_bytes = d["downloaded_bytes"]
            total_bytes = d["total_bytes"] if "total_bytes" in d else (d["total_bytes_estimate"] if "total_bytes_estimate" in d else None)
            self.__progressBar.updateProgressBar(f"Downloading ({int((downloaded_bytes / total_bytes) * 100)}%)", (downloaded_bytes, total_bytes))
            # print(f"Track {self.title()} is downloading: {downloaded_bytes} / {total_bytes if total_bytes is not None else '???'}")
        elif d["status"] == "error":
            print(f"Track {self.title()} had an error while downloading")
            self.__progressBar.updateProgressBar(f"Error", (0, 1))
        elif d["status"] == "finished":
            print(f"Track {self.title()} finished downloading, and is available at {d['filename']}")
            self.__progressBar.updateProgressBar(f"Processing", (0, 0))

    def downloadAsMP3(self):
        self.__downloadThread = TrackDownloaderThread(self)

        self.__downloadThread.statusUpdated.connect(self.updateProgress)
        self.__downloadThread.startingProcessing.connect(lambda: self.__progressBar.updateProgressBar("Processing", (0,0)))
        self.__downloadThread.allDone.connect(lambda: self.__progressBar.updateProgressBar("Done", (1,1)))

        self.__downloadThread.start()


class TrackDownloaderThread(QtCore.QThread):
    statusUpdated = QtCore.pyqtSignal(object)

    startingProcessing = QtCore.pyqtSignal()
    allDone = QtCore.pyqtSignal()

    def __init__(self, parent):
        super(TrackDownloaderThread, self).__init__(parent)
        self.parent = parent


    def updateProgress(self, d):
        self.statusUpdated.emit(d)

    def run(self):
        self.downloadAsMP3Thread()

    def downloadAsMP3Thread(self):
        download_mp3_options = {
            'format': 'bestaudio/best',
            'outtmpl': f"{self.parent.album()}/{self.parent.title()}.",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'prefer_ffmpeg': True,
            'keepvideo': False,
            'quiet': True,
            'progress_hooks': [self.updateProgress],
        }

        with youtube_dl.YoutubeDL(download_mp3_options) as ydl:
            ydl.download([self.parent.url()])

        self.setMP3Metadata()

    def setMP3Metadata(self):
        self.startingProcessing.emit()
        mp3_file = ID3(f"{self.parent.album()}/{self.parent.title()}.mp3")
        mp3_file['TPE1'] = TPE1(encoding=3, text=self.parent.artist())
        mp3_file['TPE2'] = TPE2(encoding=3, text=self.parent.artist())
        mp3_file['TPE3'] = TPE2(encoding=3, text=self.parent.artist())
        mp3_file['TIT2'] = TALB(encoding=3, text=self.parent.title())
        mp3_file['TALB'] = TALB(encoding=3, text=self.parent.album())
        mp3_file['TYER'] = TYER(encoding=3, text=self.parent.year())
        mp3_file['TCON'] = TCON(encoding=3, text=self.parent.genre())

        if self.parent.trackIndex() != (0,0):
            mp3_file["TRCK"] = TRCK(encoding=3, text=f"{self.parent.trackIndex()[0]}/{self.parent.trackIndex()[1]}")

        if self.parent.albumArtPath() != "":
            with open(self.parent.albumArtPath(), 'rb') as albumart:
                mp3_file['APIC'] = APIC(
                            encoding=3,
                            mime='image/png',
                            type=3, desc=u'Cover',
                            data=albumart.read()
                            ) 


        print(f"TPE1={self.parent.artist()}, TIT2={self.parent.title()}, TALB={self.parent.album()}")
        mp3_file.save()
        self.allDone.emit()

class ArtworkPicker(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.setupUI()
        self.setArtworkPath("SpiritOfJustice.png")


    def setupUI(self):
        self.__layout = QtWidgets.QVBoxLayout()
        self.__layout.setContentsMargins(0,0,0,0)

        self.__horizLayout = QtWidgets.QHBoxLayout()
        self.__filePathEditor = QtWidgets.QLineEdit()
        self.__filePathEditor.textEdited.connect(self.setArtworkPath)
        self.__browseButton = QtWidgets.QPushButton("Browse...")
        self.__browseButton.clicked.connect(self.openFileLocator)

        self.__horizLayout.addWidget(self.__filePathEditor)
        self.__horizLayout.addWidget(self.__browseButton)

        self.__artworkPreview = QtWidgets.QLabel("No artwork selected")
        # self.__artworkPreview.setFrameRect(QtCore.QRect(0,0,128,128))


        self.__layout.addLayout(self.__horizLayout)
        self.__layout.addWidget(self.__artworkPreview)
        self.setLayout(self.__layout)

    def artworkPath(self):
        return self.__artworkPath

    def setArtworkPath(self, filename):
        self.__artworkPath = filename
        self.__filePathEditor.setText(filename)
        self.updatePreview()

    def updatePreview(self):
        previewPixmap = QtGui.QPixmap(self.__artworkPath)
        if not previewPixmap.isNull():
            previewPixmap = previewPixmap.scaledToHeight(128, QtCore.Qt.SmoothTransformation)
            self.__artworkPreview.setPixmap(previewPixmap)
            self.__artworkPreview.setScaledContents(False)
        else:
            self.__artworkPreview.clear()
            self.__artworkPreview.setText("Not a valid image")

    def openFileLocator(self):
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self,"Select an album artwork file", "","PNG Files (*.png)")
        if fileName:
            self.setArtworkPath(fileName)
        

class ProgressIndicator(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.setupUI()

    def setupUI(self):
        self.__layout = QtWidgets.QHBoxLayout()

        self.__label = QtWidgets.QLabel("Idle")
        self.__bar = QtWidgets.QProgressBar()

        self.__layout.addWidget(self.__label)
        self.__layout.addWidget(self.__bar)
        self.setLayout(self.__layout)

    def updateProgressBar(self, text, progress):
        if progress[1] is None: progress[1] = 0
        self.__label.setText(text)
        self.__bar.setRange(progress[0], progress[1])
        self.__bar.setValue(progress[0])

class MyWindow(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)

        self.track_list: List[TrackItem] = []

        self.leftHandQueue = QtWidgets.QTreeWidget()
        self.leftHandQueue.setHeaderLabels(["Title", "Duration", "Progress"])

        self.rightHandDetailsWidget = QtWidgets.QWidget()

        self.rightHandDetailsLayout = QtWidgets.QVBoxLayout()

        self.overallLayout = QtWidgets.QSplitter()
        self.overallLayout.addWidget(self.leftHandQueue)
        self.overallLayout.addWidget(self.rightHandDetailsWidget)
        self.setCentralWidget(self.overallLayout)

        self.setUpRightHandSide()

    def setUpRightHandSide(self):
        ## Set up Playlist URL box
        self.urlGroupBox = QtWidgets.QGroupBox("Playlist URL")
        self.urlGroupBox.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)

        self.urlGroupBox_lineEntry = QtWidgets.QLineEdit("https://www.youtube.com/playlist?list=PLtPXiJedNjDFfsaMKnhsJyOZH823bXzMt")
        self.urlGroupBox_goButton = QtWidgets.QPushButton(">")
        self.urlGroupBox_goButton.clicked.connect(self.downloadTrackList)

        self.urlEntryLayout = QtWidgets.QHBoxLayout()
        self.urlEntryLayout.addWidget(self.urlGroupBox_lineEntry)
        self.urlEntryLayout.addWidget(self.urlGroupBox_goButton)
        self.urlGroupBox.setLayout(self.urlEntryLayout)

        ## Set up Per-Album Data
        self.albumDataGroupBox = QtWidgets.QGroupBox("Album Information")
        self.albumDataGroupBox.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.MinimumExpanding)

        self.songNameRegexLineEdit = QtWidgets.QLineEdit("^(.*)[\s*]-")
        self.albumDataGroupBox_albumName = QtWidgets.QLineEdit("Phoenix Wright: Ace Attorney − Spirit of Justice")
        self.albumDataGroupBox_artistName = QtWidgets.QLineEdit("Capcom")
        self.albumDataGroupBox_year = QtWidgets.QLineEdit("2016")
        self.albumDataGroupBox_artworkPicker = ArtworkPicker()

        self.albumDataLayout = QtWidgets.QFormLayout()
        self.albumDataLayout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Title Pattern"), self.songNameRegexLineEdit)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Album"), self.albumDataGroupBox_albumName)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Artist"), self.albumDataGroupBox_artistName)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Year"), self.albumDataGroupBox_year)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Artwork"), self.albumDataGroupBox_artworkPicker)
        self.albumDataGroupBox.setLayout(self.albumDataLayout)


        ## Download button
        self.previewButton = QtWidgets.QPushButton("Preview")
        self.previewButton.clicked.connect(self.updatePreview)
        self.downloadButton = QtWidgets.QPushButton("Download")
        self.downloadButton.clicked.connect(self.downloadTracks)

        ## Final stuff
        self.rightHandDetailsLayout.addWidget(self.urlGroupBox)
        self.rightHandDetailsLayout.addWidget(self.albumDataGroupBox)

        self.rightHandDetailsLayout.addWidget(self.previewButton)
        self.rightHandDetailsLayout.addWidget(self.downloadButton)

        self.rightHandDetailsWidget.setLayout(self.rightHandDetailsLayout)
    
    def downloadTrackList(self):
        print("Download track list")
        data = get_names_in_playlist(self.urlGroupBox_lineEntry.text())
        self.track_list.clear()

        trackIndex = 1
        for track in data:
            self.track_list.append(TrackItem(self, track, (trackIndex, len(data))))
            trackIndex += 1

        self.updatePreview()
        

    def updatePreview(self):
        # Apply our changes to each item in the queue
        artistName = self.albumDataGroupBox_artistName.text()
        albumName = self.albumDataGroupBox_albumName.text()
        albumYear = self.albumDataGroupBox_year.text()
        regexPattern = self.songNameRegexLineEdit.text()
        albumArtPath = self.albumDataGroupBox_artworkPicker.artworkPath()
        for track in self.track_list:
            track.applyRegexTitlePattern(regexPattern)
            track.setArtist(artistName)
            track.setAlbum(albumName)
            track.setYear(albumYear)
            track.setAlbumArtPath(albumArtPath)
            track.setProgressBar(ProgressIndicator())
        self.populateLeftHandSideWithTracks()
        

    def populateLeftHandSideWithTracks(self):
        print("Populate list of tracks")

        while self.leftHandQueue.takeTopLevelItem(0) is not None: pass

        for track in self.track_list:
            new_list_item = QtWidgets.QTreeWidgetItem()
            new_list_item.setText(0, track.title())
            new_list_item.setText(1, str(track.readableDuration()))
        
            self.leftHandQueue.addTopLevelItem(new_list_item)
            self.leftHandQueue.setItemWidget(new_list_item, 2, track.progressBar())


    def downloadTracks(self):
        # update track metadata
        self.updatePreview()

        # check if the target directory exists, make it if not
        albumName = self.albumDataGroupBox_albumName.text()
        if not os.path.isdir(albumName): os.mkdir(albumName)

        for track in self.track_list:
            track.downloadAsMP3()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())