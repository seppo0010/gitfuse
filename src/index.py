#!/usr/bin/env python
# -*- coding: utf-8 -*-
import errno
import fuse
import stat
import time
import os
import sys
import ConfigParser
from git import *
from multiprocessing import Process

fuse.fuse_python_api = (0, 2)



def shellquote(s):
	return "\"" + s.replace("\"", "\\\"") + "\""

class GitFuse(fuse.Fuse):
	basePath = ""
	openFiles = {}

	def __init__(self, *args, **kw):
		fuse.Fuse.__init__(self, *args, **kw)
		home = os.getenv('HOME');
		if home == None:
			sys.exit('Unable to read configuration file');

		config = ConfigParser.ConfigParser()
		config.read([home + '/.gitfuserc'])

		try:
			self.basePath = config.get('gitfusetest', 'path'); #TODO: Remove hardcoded repository name
			if self.basePath.count('~',0,1) == 1:
				self.basePath = self.basePath.replace('~',home,1)
			self.basePath = self.basePath.rstrip('/') + '/'
		except ConfigParser.Error:
			sys.exit('Unable to find repository path');

		self.repo = Repo(self.basePath)
		assert self.repo.bare == False

		self.syncTimer = Process(None, self.gitsync)
		self.syncTimer.start()


	def getattr(self, path):
		self.debug(str(['getattr', path]))
		realpath = self.getpath(path)
		ret = os.lstat(realpath)
		return ret

	def mknod(self, path, mode, dev):
		self.debug(str(['mknod', path, mode, dev]))
		realpath = self.getpath(path)
		fp = open(realpath, 'w', mode)
		fp.close()
		index = self.repo.index
		index.add([realpath])
		index.commit('Created file')
		return 0

	def open(self, path, flags):
		self.debug(str(['open', path, flags]))
		openmode = self.getmodeforflag(flags)
		if (path in self.openFiles and openmode in self.openFiles[path]):
			self.openFiles[path][openmode]["count"] += 1
			return 0

		fp = open(self.getpath(path), openmode)
		if (path not in self.openFiles):
			self.openFiles[path] = {}
		self.openFiles[path][openmode] = {"fp":fp,"count":1}
		return 0

	def read(self, path, size, offset):
		self.debug(str(['read', path, size, offset]))
		fp = self.openFiles[path]['r+']["fp"]
		fp.seek(offset, os.SEEK_SET)
		return fp.read(size)

	def release(self, path, flags):
		self.debug(str(['release', path, flags]))
		openmode = self.getmodeforflag(flags)
		if (path in self.openFiles and openmode in self.openFiles[path]):
			self.openFiles[path][openmode]["count"] -= 1
			if (self.openFiles[path][openmode]["count"] == 0):
				self.openFiles[path][openmode]["fp"].close()
				if (openmode == 'a+'):
					index.add([self.getpath(path)])
					index.commit('Edited file')
				del self.openFiles[path][openmode]
		return

	def write(self, path, buf, offset):
		self.debug(str(['write', path, buf, offset]))
		fp = self.openFiles[path]['a+']["fp"]

		fp.truncate(offset)
		fp.write(str(buf))
		fp.flush()
		os.fsync(fp.fileno())
		return len(buf)

	def truncate(self, path, size):
		self.debug(str(['truncate', path, size]))
		self.open(path, 1)
		fp = self.openFiles[path]['a+']["fp"]
		ret = fp.truncate(size)
		self.release(path, 1)
		return ret

	def utime(self, path, times):
		self.debug(str(['utime', path, times]))
		return os.utime(self.getpath(path), times)

	def mkdir(self, path, mode):
		self.debug(str(['mkdir', path, mode]))
		return os.mkdir(self.getpath(path), mode)

	def rmdir(self, path):
		self.debug(str(['rmdir', path]))
		return os.rmdir(self.getpath(path))

	def rename(self, pathfrom, pathto):
		self.debug(str(['rename', pathfrom, pathto]))
		src = self.getpath(pathfrom)
		target = self.getpath(pathto)
		ret = os.rename(src, target)
		index = self.repo.index
		index.rm([src])
		index.add([target])
		index.commit('Renamed file')
		return ret

	def fsync(self, path, isfsyncfile):
		self.debug(str(['fsync', path, isfsyncfile]))
		fp = self.openFiles[path][1]["fp"]
		return os.fsync(fp)

	def readdir(self, path, offset):
		self.debug(str(['readdir', path, offset]))
		for e in '.', '..':
			yield fuse.Direntry(e);
		for e in os.listdir(self.basePath + path):
			if (path != '/' or e != '.git'):
				yield fuse.Direntry(e);

	def chmod(self, path, mode):
		self.debug(str(['chmod', path, mode]))
		realpath = self.getpath(path)
		ret = os.chmod(realpath, mode)
		index = self.repo.index
		index.add([realpath])
		index.commit('Changed file permissions')
		return ret

	def unlink(self, path):
		self.debug(str(['unlink', path]))
		realpath = self.getpath(path)
		ret = os.unlink(realpath)
		index = self.repo.index
		index.rm([realpath])
		index.commit('Deleted file')
		return ret

	def chown(self, path, uid, gid):
		self.debug(str(['chown', path, uid, gid]))
		realpath = self.getpath(path)
		return os.chown(realpath, uid, gid)

#	def statfs(self):
#		self.debug(str(['statfs']))
#		return -errno.ENOSYS

	def link(self, targetPath, linkPath):
		self.debug(str(['link', targetPath, linkPath]))
		return -errno.ENOSYS

	def readlink(self, path):
		self.debug(str(['readlink', path]))
		realpath = self.getpath(path)
		return os.readlink(realpath)

	def symlink(self, targetPath, linkPath):
		self.debug(str(['symlink', targetPath, linkPath]))
		target = self.getpath(targetPath)
		link = self.getpath(linkPath)
		ret = os.symlink(target, link)
		index = self.repo.index
		index.add([realpath])
		index.commit('Created symlink')
		return ret

	def getmodeforflag(self, flag):
		if flag & 1 > 0:
			return 'a+'
		else:
			return 'r+'

	def getpath(self, path):
		return self.basePath + path.lstrip('/');

	def debug(self, text):
		return
		f = open('/tmp/workfile', 'a+')
		f.write(text)
		f.write("\n")
		f.close()

	def gitsync(self):
		try:
			origin = self.repo.remotes.origin
			while True:
				time.sleep(60)
				origin.fetch()
				origin.pull()
				origin.push()
		except AttributeError:
			pass


if __name__ == '__main__':
	fs = GitFuse()
	fs.parse(errex=1)
	fs.multithreaded = True
	fs.main()
