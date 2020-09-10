from __future__ import unicode_literals
import youtube_dl
import re

from PyQt5 import QtWidgets
import sys
from datetime import timedelta

from typing import List

from mutagen.easyid3 import EasyID3


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

class TrackItem:
    def __init__(self, trackData={"title": "TITLE", "duration": 0}):
        self.__rawName = trackData["title"]
        self.__trackTitle = trackData["title"]
        self.__trackArtist = "ARTIST"
        self.__trackAlbum = "ALBUM"
        self.__trackYear = "YEAR"
        self.__duration = trackData["duration"]

        self.__url = trackData["webpage_url"]

    def title(self):
        return self.__trackTitle

    def artist(self):
        return self.__trackArtist

    def album(self):
        return self.__trackAlbum

    def year(self):
        return self.__year

    def rawName(self):
        return self.__rawName

    def duration(self):
        return self.__duration

    def readableDuration(self):
        return timedelta(seconds=self.duration())

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

            print(f"Track {self.title()} is downloading: {downloaded_bytes} / {total_bytes if total_bytes is not None else '???'}")
        elif d["status"] == "error":
            print(f"Track {self.title()} had an error while downloading")
        elif d["status"] == "finished":
            print(f"Track {self.title()} finished downloading, and is available at {d['filename']}")

    def downloadAsMP3(self):
        download_mp3_options = {
            'format': 'bestaudio/best',
            'outtmpl': f"{self.title()}.",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'prefer_ffmpeg': True,
            'keepvideo': False,
            # 'quiet': True,
            'verbose': True,
            'progress_hooks': [self.updateProgress],
        }

        with youtube_dl.YoutubeDL(download_mp3_options) as ydl:
            ydl.download([self.url()])

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

        self.urlGroupBox_lineEntry = QtWidgets.QLineEdit("https://www.youtube.com/playlist?list=PLtPXiJedNjDFfsaMKnhsJyOZH823bXzMt")
        self.urlGroupBox_goButton = QtWidgets.QPushButton(">")
        self.urlGroupBox_goButton.clicked.connect(self.downloadTrackList)

        self.urlEntryLayout = QtWidgets.QHBoxLayout()
        self.urlEntryLayout.addWidget(self.urlGroupBox_lineEntry)
        self.urlEntryLayout.addWidget(self.urlGroupBox_goButton)
        self.urlGroupBox.setLayout(self.urlEntryLayout)

        ## Set up Per-Album Data
        self.albumDataGroupBox = QtWidgets.QGroupBox("Album Information")
        self.songNameRegexLineEdit = QtWidgets.QLineEdit("^(.*)[\s*]-")
        self.albumDataGroupBox_albumName = QtWidgets.QLineEdit("Phoenix Wright: Ace Attorney − Spirit of Justice")
        self.albumDataGroupBox_artistName = QtWidgets.QLineEdit("Capcom")
        self.albumDataGroupBox_year = QtWidgets.QLineEdit("2016")

        self.albumDataLayout = QtWidgets.QFormLayout()
        self.albumDataLayout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Title Pattern"), self.songNameRegexLineEdit)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Album"), self.albumDataGroupBox_albumName)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Artist"), self.albumDataGroupBox_artistName)
        self.albumDataLayout.addRow(QtWidgets.QLabel("Year"), self.albumDataGroupBox_year)
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
        for track in data:
            self.track_list.append(TrackItem(track))
        self.updatePreview()

    def updatePreview(self):
        # Apply our changes to each item in the queue
        artistName = self.albumDataGroupBox_artistName.text()
        albumName = self.albumDataGroupBox_albumName.text()
        albumYear = self.albumDataGroupBox_year.text()
        regexPattern = self.songNameRegexLineEdit.text()
        for track in self.track_list:
            track.applyRegexTitlePattern(regexPattern)
            track.setArtist(artistName)
            track.setAlbum(albumName)
            track.setYear(albumYear)
        self.populateLeftHandSideWithTracks()

    def populateLeftHandSideWithTracks(self):
        print("Populate list of tracks")

        while self.leftHandQueue.takeTopLevelItem(0) is not None: pass

        for track in self.track_list:
            new_list_item = QtWidgets.QTreeWidgetItem()
            new_list_item.setText(0, track.title())
            new_list_item.setText(1, str(track.readableDuration()))
        
            self.leftHandQueue.addTopLevelItem(new_list_item)
            self.leftHandQueue.setItemWidget(new_list_item, 2, QtWidgets.QProgressBar())

    def downloadTracks(self):
        for track in self.track_list:
            track.downloadAsMP3()


# print(get_names_in_playlist("https://www.youtube.com/watch?v=WJyaIvAGwqI&"))
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())