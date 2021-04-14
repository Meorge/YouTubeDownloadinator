from __future__ import unicode_literals
import youtube_dl
import re
import threading
import json

from PyQt5 import QtWidgets, QtGui, QtCore
import sys
from datetime import timedelta

from typing import List

import os.path
from mutagen.id3 import ID3, TPE1, TPE2, TIT2, TRCK, TALB, APIC, TYER, TCON, TRCK
from mutagen.mp4 import MP4, MP4Cover

def updateProgress(d):
    print(d)

download_metadata_options = {
    'writesubtitles': True,
    'format': 'mp4',
    'writethumbnail': True,
    'sleep_interval': 0,
    'max_sleep_interval': 0,
    'skip_download': True,
    'simulate': True,
    'progress_hooks': [updateProgress],
}

download_all_at_once = False

important_keys = ["title", "duration", "webpage_url", "index"]

class TrackItem(QtCore.QObject):
    def __init__(self, parent, trackData={"title": "TITLE", "duration": 0}, trackIndex = (0,0)):
        super(TrackItem, self).__init__(parent)
        self.__trackData = { key: trackData[key] for key in important_keys }
        


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

    def trackData(self):
        return self.__trackData

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
            self.__progressBar.updateProgressBar(f"Processing", (0, 0))

    def downloadAsMP3(self):
        self.__downloadThread = TrackDownloaderThread(self)

        self.__downloadThread.statusUpdated.connect(self.updateProgress)
        self.__downloadThread.startingProcessing.connect(lambda: self.__progressBar.updateProgressBar("Processing", (0,0)))
        self.__downloadThread.allDone.connect(self.allDoneDownloading)

        self.__downloadThread.start()

    def allDoneDownloading(self):
        self.__progressBar.updateProgressBar("Done", (1,1))
        self.parent().trackCompleted()

class PlaylistMetadataDownloaderThread(QtCore.QThread):
    complete = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(object)

    def __init__(self, parent, url):
        super(PlaylistMetadataDownloaderThread, self).__init__(parent)
        self.parent = parent
        self.url = url

    def run(self):
        try:
            with youtube_dl.YoutubeDL(download_metadata_options) as ydl:
                ie_result = ydl.extract_info(self.url, False)
                if "_type" in ie_result: # it's a playlist

                    index = 1
                    for i in ie_result["entries"]:
                        i["index"] = index
                        index += 1

                    self.complete.emit(ie_result["entries"])
                else: # it's a single video
                    self.complete.emit(ie_result)
        except Exception as e:
            print(e)
            self.error.emit(e)

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
            'outtmpl': self.parent.album() + "/" + self.parent.title().replace('/', '\/') + ".",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '320',
            }],
            'prefer_ffmpeg': True,
            'keepvideo': False,
            'quiet': True,
            'progress_hooks': [self.updateProgress],
        }

        with youtube_dl.YoutubeDL(download_mp3_options) as ydl:
            ydl.download([self.parent.url()])

        self.setM4AMetadata()


    def setM4AMetadata(self):
        self.startingProcessing.emit()
        tags = MP4(f"{self.parent.album()}/{self.parent.title()}.m4a").tags
        tags['\xa9nam'] = self.parent.title()
        tags['\xa9alb'] = self.parent.album()
        tags['\xa9ART'] = self.parent.artist()
        tags['aART'] = self.parent.artist()
        tags['\xa9wrt'] = self.parent.artist()
        tags['\xa9day'] = self.parent.year()
        tags['trkn'] = [self.parent.trackIndex()]

        with open(self.parent.albumArtPath(), 'rb') as albumart:
            tags['covr'] = [MP4Cover(albumart.read(), MP4Cover.FORMAT_PNG)]

        tags.save(f"{self.parent.album()}/{self.parent.title()}.m4a")


        self.allDone.emit()

    def setMP3Metadata(self):
        self.startingProcessing.emit()
        mp3_file = ID3(f"{self.parent.album()}/{self.parent.title()}.mp3")
        mp3_file['TPE1'] = TPE1(encoding=3, text=self.parent.artist())
        mp3_file['TPE2'] = TPE2(encoding=3, text=self.parent.artist())
        mp3_file['TPE3'] = TPE2(encoding=3, text=self.parent.artist())
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
        self.__layout.setContentsMargins(5,0,5,0)

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
        self.current_track_index = 0
        self.downloadingInProgress = True
        self.tracksCompleted = 0

        self.leftHandQueue = QtWidgets.QTreeWidget()
        self.leftHandQueue.setHeaderLabels(["#", "Title", "Duration", "Progress"])
        self.leftHandQueue.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        self.rightHandDetailsWidget = QtWidgets.QWidget()

        self.rightHandDetailsLayout = QtWidgets.QVBoxLayout()

        self.overallLayout = QtWidgets.QSplitter()
        self.overallLayout.addWidget(self.leftHandQueue)
        self.overallLayout.addWidget(self.rightHandDetailsWidget)
        self.setCentralWidget(self.overallLayout)

        self.setWindowTitle("YouTube Downloadinator")

        self.setUpRightHandSide()

    def setUpRightHandSide(self):
        ## Set up Save/Load box
        self.saveLoadBox = QtWidgets.QGroupBox("Configurations")
        self.saveLoadBox.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        self.saveLoadBox_load = QtWidgets.QPushButton("Load")
        self.saveLoadBox_load.clicked.connect(self.loadConfig)
        self.saveLoadBox_save = QtWidgets.QPushButton("Save")
        self.saveLoadBox_save.clicked.connect(self.saveConfig)
        self.saveLoadLayout = QtWidgets.QHBoxLayout()
        self.saveLoadLayout.addWidget(self.saveLoadBox_load)
        self.saveLoadLayout.addWidget(self.saveLoadBox_save)
        self.saveLoadBox.setLayout(self.saveLoadLayout)

        ## Set up Playlist URL box
        self.urlGroupBox = QtWidgets.QGroupBox("Playlist URL")
        self.urlGroupBox.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)

        self.urlGroupBox_lineEntry = QtWidgets.QLineEdit("https://www.youtube.com/playlist?list=PLtPXiJedNjDFfsaMKnhsJyOZH823bXzMt")
        self.urlGroupBox_goButton = QtWidgets.QPushButton("Download metadata")
        self.urlGroupBox_goButton.clicked.connect(self.downloadTrackList)

        self.urlEntryLayout = QtWidgets.QVBoxLayout()
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
        self.rightHandDetailsLayout.addWidget(self.saveLoadBox)
        self.rightHandDetailsLayout.addSpacing(10)
        self.rightHandDetailsLayout.addWidget(self.urlGroupBox)
        self.rightHandDetailsLayout.addSpacing(10)
        self.rightHandDetailsLayout.addWidget(self.albumDataGroupBox)
        self.rightHandDetailsLayout.addSpacing(10)

        self.rightHandDetailsLayout.addWidget(self.previewButton)
        self.rightHandDetailsLayout.addWidget(self.downloadButton)

        self.rightHandDetailsWidget.setLayout(self.rightHandDetailsLayout)

        self.updatePreview()

    def saveConfig(self):
        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self,"Save configuration file","","JSON file (*.json)")
        if not fileName:
            return
        _file = open(fileName, "w")
        json.dump(self.getConfigDictionary(), _file, indent=4)
        _file.close()

    def loadConfig(self):
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self,"Open configuration file","","JSON file (*.json)")
        if not fileName:
            return
        _file = open(fileName, "r")
        self.loadConfigDictionary(json.load(_file))
        _file.close()

    def loadConfigDictionary(self, dict):
        self.urlGroupBox_lineEntry.setText(dict["playlist_url"])
        self.songNameRegexLineEdit.setText(dict["title_pattern"])
        self.albumDataGroupBox_artistName.setText(dict["artist"])
        self.albumDataGroupBox_albumName.setText(dict["album"])
        self.albumDataGroupBox_year.setText(dict["year"])
        self.albumDataGroupBox_artworkPicker.setArtworkPath(dict["album_art_path"])
        
        for track_item in dict["tracks"]:
            self.track_list.append(TrackItem(self, track_item, (track_item["index"], len(dict["tracks"]))))

        self.updatePreview()

    def getConfigDictionary(self):
        return {
            "playlist_url": self.urlGroupBox_lineEntry.text(),
            "title_pattern": self.songNameRegexLineEdit.text(),
            "artist": self.albumDataGroupBox_artistName.text(),
            "album": self.albumDataGroupBox_albumName.text(),
            "year": self.albumDataGroupBox_year.text(),
            "album_art_path": self.albumDataGroupBox_artworkPicker.artworkPath(),
            "tracks": [track_item.trackData() for track_item in self.track_list]
        }
    
    def downloadTrackList(self):
        print("Download track list")
        playlistMetadataThread = PlaylistMetadataDownloaderThread(self, self.urlGroupBox_lineEntry.text())
        playlistMetadataThread.complete.connect(self.trackListDownloaded)
        playlistMetadataThread.start()

        self.urlGroupBox_goButton.setEnabled(False)
        self.saveLoadBox.setEnabled(False)
        self.urlGroupBox_lineEntry.setEnabled(False)
        self.repaint()

    def trackListDownloaded(self, data):
        self.track_list.clear()

        for track in data:
            self.track_list.append(TrackItem(self, track, (track["index"], len(data))))

        self.updatePreview()

        self.urlGroupBox_goButton.setEnabled(True)
        self.saveLoadBox.setEnabled(True)
        self.urlGroupBox_lineEntry.setEnabled(True)
        self.repaint()


    def setButtonsEnabled(self, enabled):
        # self.albumDataGroupBox.setEnabled(enabled)
        self.previewButton.setEnabled(enabled)
        self.downloadButton.setEnabled(enabled)
        self.repaint()
        

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

        self.setButtonsEnabled(len(self.track_list) != 0)

        for track in self.track_list:
            new_list_item = QtWidgets.QTreeWidgetItem()
            new_list_item.setText(0, str(track.trackIndex()[0]))
            new_list_item.setText(1, track.title())
            new_list_item.setText(2, str(track.readableDuration()))
        
            self.leftHandQueue.addTopLevelItem(new_list_item)
            self.leftHandQueue.setItemWidget(new_list_item, 3, track.progressBar())


    def downloadTracks(self):
        # update track metadata
        self.updatePreview()

        # check if the target directory exists, make it if not
        albumName = self.albumDataGroupBox_albumName.text()
        if not os.path.isdir(albumName): os.mkdir(albumName)

        self.downloadingInProgress = True
        self.tracksCompleted = 0

        self.urlGroupBox.setEnabled(False)
        self.albumDataGroupBox.setEnabled(False)
        self.setButtonsEnabled(False)


        if download_all_at_once:
            for track in self.track_list:
                track.downloadAsMP3()

        else:
            # don't download all at once
            # Instead, start by downloading the first one
            # and once that's done, start downloading the next one...
            self.current_track_index = 0
            self.track_list[self.current_track_index].downloadAsMP3()

    def trackCompleted(self):
        self.tracksCompleted += 1
        if self.tracksCompleted == len(self.track_list):
            self.allTracksCompleted()
            return

        if not download_all_at_once:
            self.current_track_index += 1
            self.track_list[self.current_track_index].downloadAsMP3()

    def allTracksCompleted(self):
        self.downloadingInProgress = False
        self.urlGroupBox.setEnabled(True)
        self.albumDataGroupBox.setEnabled(True)
        self.setButtonsEnabled(True)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())