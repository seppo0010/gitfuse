#!/usr/bin/env python
# -*- coding: utf-8 -*-
import errno
import fuse
import stat
import time
import os
import sys
import ConfigParser

fuse.fuse_python_api = (0, 2)

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
		except ConfigParser.Error:
			sys.exit('Unable to find repository path');

	def getattr(self, path):
		self.debug(str(['getattr', path]))
		return os.stat(self.getpath(path))

	def mknod(self, path, mode, dev):
		self.debug(str(['mknod', path, mode, dev]))
		realpath = self.getpath(path)
		fp = open(realpath, 'w', mode)
		fp.close()
		self.git('add', realpath)
		self.git('commit -m "Created file"', realpath)
		return 0

	def open(self, path, flags):
		self.debug(str(['open', path, flags]))
		if (path in self.openFiles and flags in self.openFiles[path]):
			self.openFiles[path][flags]["count"] += 1
			return 0

		openflag = 'a+'
		if (flags == 0):
			openflag = 'r+'
		fp = open(self.getpath(path), openflag)
		if (path not in self.openFiles):
			self.openFiles[path] = {}
		self.openFiles[path][flags] = {"fp":fp,"count":1}
		return 0

	def read(self, path, size, offset):
		self.debug(str(['read', path, size, offset]))
		fp = self.openFiles[path][0]["fp"]
		fp.seek(offset, os.SEEK_SET)
		return fp.read(size)

	def release(self, path, flags):
		self.debug(str(['release', path, flags]))
		if (path in self.openFiles and flags in self.openFiles[path]):
			self.openFiles[path][flags]["count"] -= 1
			if (self.openFiles[path][flags]["count"] == 0):
				self.openFiles[path][flags]["fp"].close()
				if (flags == 1):
					self.git('commit -m "Edited file"', self.getpath(path))
				del self.openFiles[path][flags]
		return

	def write(self, path, buf, offset):
		self.debug(str(['write', path, buf, offset]))
		fp = self.openFiles[path][1]["fp"]

		fp.truncate(offset)
		fp.write(str(buf))
		fp.flush()
		os.fsync(fp.fileno())
		return len(buf)

	def truncate(self, path, size):
		self.debug(str(['truncate', path, size]))
		fp = self.openFiles[path][1]["fp"]
		return fp.truncate(size)

	def utime(self, path, times):
		self.debug(str(['utime', path, times]))
		return os.utime(self.getpath(path), times)

	def mkdir(self, path, mode):
		self.debug(str(['mkdir', path, mode]))
		return os.mkdir(self.getpath(path, mode))

	def rmdir(self, path):
		self.debug(str(['rmdir', path]))
		return os.rmdir(self.getpath(path))

	def rename(self, pathfrom, pathto):
		self.debug(str(['rename', pathfrom, pathto]))
		src = self.getpath(pathfrom)
		target = self.getpath(pathto)
		ret = os.rename(src, target)
		self.git('rm', src)
		self.git('add', target)
		self.git('commit -m "Renamed file" ', src + ' ' +target)
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
			yield fuse.Direntry(e);

	def chmod(self, path, mode):
		self.debug(str(['chmod', path, mode]))
		realpath = self.getpath(path)
		ret = os.chmod(realpath, mode)
		self.git('add', realpath)
		self.git('commit -m "Changed file permissions"', realpath)
		return ret

	def getpath(self, path):
		return self.basePath + path;

	def debug(self, text):
		return
		f = open('/tmp/workfile', 'a+')
		f.write(text)
		f.write("\n")
		f.close()

	def git(self, command, file):
		os.chdir(self.basePath)
		os.system('git ' + command + ' ' + file)

if __name__ == '__main__':
	fs = GitFuse()
	fs.parse(errex=1)
	fs.multithreaded = False
	fs.main()
