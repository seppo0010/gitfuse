#!/usr/bin/env python

__all__ = ['Reposymlink', 'History']

def Reposymlink(repo):
	import reposymlink
	return reposymlink.Reposymlink(repo)

def History(repo):
	import history
	return history.History(repo)
