#!/usr/bin/env python
# -*- coding: utf-8 -*-
import errno
import fuse
import stat
import time
import os
import sys
import ConfigParser
from multiprocessing import Process

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
			self.basePath = self.basePath.rstrip('/') + '/'
		except ConfigParser.Error:
			sys.exit('Unable to find repository path');

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
		return os.mkdir(self.getpath(path), mode)

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

	def unlink(self, path):
		self.debug(str(['unlink', path]))
		realpath = self.getpath(path)
		ret = os.unlink(realpath)
		self.git('rm', realpath)
		self.git('commit -m "Deleted file"', realpath)
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
		self.git('add', link)
		self.git('commit -m "Created symlink"', link)
		return ret

	def getpath(self, path):
		return self.basePath + path.lstrip('/');

	def debug(self, text):
		return
		f = open('/tmp/workfile', 'a+')
		f.write(text)
		f.write("\n")
		f.close()

	def git(self, command, file):
		os.chdir(self.basePath)
		os.system('git ' + command + ' ' + file + '>/dev/null 2>/dev/null')

	def gitsync(self):
		while True:
			time.sleep(60)
			os.chdir(self.basePath)
			os.system('git pull >/dev/null 2>/dev/null')
			os.system('git push >/dev/null 2>/dev/null')

if __name__ == '__main__':
	fs = GitFuse()
	fs.parse(errex=1)
	fs.multithreaded = True
	fs.main()
