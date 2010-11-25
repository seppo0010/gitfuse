#!/usr/bin/env python

import fuse
import stat
import time
import os
import re
import errno
import git

class History(object):
	fs = None
	openFiles = {}

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
			fstat = os.lstat(self.fs.basePath)
			ret = fuse.Stat()
			ret.st_mode = stat.S_IFDIR | 0755
			ret.st_nlink = 2
			ret.st_uid = fstat.st_uid
			ret.st_gid = fstat.st_gid
			ret.st_atime = int(time.time())
			ret.st_mtime = ret.st_atime
			ret.st_ctime = ret.st_atime
			return ret

		subpath = path[13:]
		if os.path.isdir(self.fs.basePath + subpath) or os.path.isfile(self.fs.basePath + subpath):
			fstat = os.lstat(self.fs.basePath + subpath)
			ret = fuse.Stat()
			ret.st_mode = stat.S_IFDIR | 0755
			ret.st_nlink = 2
			ret.st_uid = fstat.st_uid
			ret.st_gid = fstat.st_gid
			ret.st_atime = int(time.time())
			ret.st_mtime = ret.st_atime
			ret.st_ctime = ret.st_atime
			return ret
		m = re.match(r'(.+)\/([0-9a-fA-F]{40})',subpath)
		if m:
			file = m.group(1)
			revision = m.group(2)
			fstat = os.lstat(self.fs.basePath + file)
			commit = self.fs.repo.commit(revision)
			ret = fuse.Stat()
			ret.st_mode = stat.S_IFREG | (fstat.st_mode & 0777)
			ret.st_uid = fstat.st_uid
			ret.st_gid = fstat.st_gid
			ret.st_nlink = 2
			ret.st_atime = int(time.time())
			ret.st_mtime = commit.committed_date
			ret.st_ctime = commit.committed_date
			self.open([path, 0])
			if path in self.openFiles:
				ret.st_size = len(self.openFiles[path]['data'])
			self.release([path, 0])
			return ret
		return -errno.ENOENT

	def respond_open(self, params):
		return self.contains_path(params)

	def open(self, params):
		if self.fs.getmodeforflag(params[1]) == 'a+':
			return -errno.ENOENT

		path = params[0]
		if path not in self.openFiles:
			subpath = path[13:]
			m = re.match(r'(.+)\/([0-9a-fA-F]{40})',subpath)
			if m:
				file = m.group(1)
				revision = m.group(2)
				data = ''
				try:
					data = self.fs.repo.git.show(revision + ':' + file)
				except git.exc.GitCommandError:
					pass
				self.openFiles[path] = {"data":data, "count":1}
		else:
			self.openFiles[path]["count"] += 1
		return 0

	def respond_read(self, params):
		return self.contains_path(params)

	def read(self, params):
		path = params[0]
		size = params[1]
		offset = params[2]
		ret = ''
		self.open([path, 0])
		if path in self.openFiles:
			ret = self.openFiles[path]['data'][offset:size+offset]
		self.release([path, 0])
		return ret

	def respond_release(self, params):
		return self.contains_path(params)

	def release(self, params):
		path = params[0]
		if self.fs.getmodeforflag(params[1]) == 'a+':
			return -errno.ENOENT

		if path in self.openFiles:
			self.openFiles[path]["count"] -= 1
			if self.openFiles[path]["count"] == 0:
				del self.openFiles[path]
		return 0

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
