#!/usr/bin/env python

import fuse
import stat
import time
import os
import re
import errno

class History(object):
	fs = None

	def __init__(self, fs):
		self.fs = fs

	def contains_path(self, params):
		path = params[0]
		return path.startswith('/.githistory')

	def respond_getattr(self, params):
		return self.contains_path(params)
		
	def getattr(self, params):
		path = params[0]
		if path == '/.githistory':
			ret = fuse.Stat()
			ret.st_mode = stat.S_IFDIR | 0755
			ret.st_nlink = 2
			ret.st_atime = int(time.time())
			ret.st_mtime = ret.st_atime
			ret.st_ctime = ret.st_atime
			return ret

		subpath = path[13:]
		if os.path.isdir(self.fs.basePath + subpath) or os.path.isfile(self.fs.basePath + subpath):
			ret = fuse.Stat()
			ret.st_mode = stat.S_IFDIR | 0755
			ret.st_nlink = 2
			ret.st_atime = int(time.time())
			ret.st_mtime = ret.st_atime
			ret.st_ctime = ret.st_atime
			return ret
		m = re.match(r'(.+)\/([0-9a-fA-F]{40})',subpath)
		if m:
			file = m.group(1)
			revision = m.group(2)
			commit = self.fs.repo.commit(revision)
			ret = fuse.Stat()
			ret.st_mode = stat.S_IFREG | 0755
			ret.st_nlink = 2
			ret.st_atime = int(time.time())
			ret.st_mtime = commit.committed_date
			ret.st_ctime = commit.committed_date
			ret.st_size = len(self.fs.repo.git.show(revision + ':' + file))
			return ret
		return -errno.ENOENT

	def respond_open(self, params):
		return self.contains_path(params)

	def open(self, params):
		return 0

	def respond_read(self, params):
		return self.contains_path(params)

	def read(self, params):
		path = params[0]
		size = params[1]
		offset = params[2]
		subpath = path[13:]
		m = re.match(r'(.+)\/([0-9a-fA-F]{40})',subpath)
		if m:
			file = m.group(1)
			revision = m.group(2)
			data = self.fs.repo.git.show(revision + ':' + file)
			return str(data)[offset:size+offset]
		return ''

	def respond_release(self, params):
		return self.contains_path(params)

	def release(self, params):
		pass

	def readdir(self, args):
		path = args[0]
		if path == '/':
			return ['.githistory']

		if path.startswith('/.githistory') == False:
			return []

		subpath = path[13:]
		if os.path.isfile(self.fs.basePath + subpath):
			ret = []
			for f in self.fs.repo.iter_commits(None, subpath):
				ret.append(str(f))
			return ret
		else:
			return os.listdir(self.fs.basePath + subpath)
