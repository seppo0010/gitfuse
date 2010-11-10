#!/usr/bin/env python

import fuse
import stat
import time

class Reposymlink(object):
	fs = None

	def __init__(self, fs):
		self.fs = fs

	def respond_getattr(self, path):
		return path == '/.gitfuserepo'
		
	def getattr(self, path):
		ret = fuse.Stat()
		ret.st_mode = stat.S_IFLNK | 0755
		ret.st_nlink = 2
		ret.st_atime = int(time.time())
		ret.st_mtime = ret.st_atime
		ret.st_ctime = ret.st_atime
		return ret

	def respond_readlink(self, path):
		return path == '/.gitfuserepo'

	def readlink(self, path):
		return self.fs.basePath

