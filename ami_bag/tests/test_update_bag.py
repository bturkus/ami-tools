# -*- coding: utf-8 -*-

import codecs
import datetime
import hashlib
import logging
import os
import shutil
import stat
import sys
import tempfile
import unittest
from os.path import join as j
import ami_bag.bagit

import ami_bag.update_bag as update_bag

# don't let < ERROR clutter up test output
logging.basicConfig(filename="test.log", level=logging.DEBUG)


class TestSingleProcessValidation(unittest.TestCase):
  def setUp(self):
    self.tmpdir = tempfile.mkdtemp()
    if os.path.isdir(self.tmpdir):
      shutil.rmtree(self.tmpdir)
    shutil.copytree('test-data', self.tmpdir)

  def tearDown(self):
    if os.path.isdir(self.tmpdir):
      shutil.rmtree(self.tmpdir)

  def validate(self, bag, *args, **kwargs):
    return bag.validate(*args, **kwargs)

  def test_make_bag_sha1_sha256_manifest(self):
    bagit.make_bag(self.tmpdir, checksum=['sha1', 'sha256'])
    bag = update_bag.Repairable_Bag(self.tmpdir)
    # check that relevant manifests are created
    self.assertTrue(os.path.isfile(j(self.tmpdir, 'manifest-sha1.txt')))
    self.assertTrue(os.path.isfile(j(self.tmpdir, 'manifest-sha256.txt')))
    # check valid with two manifests
    self.assertTrue(self.validate(bag, fast=True))

  def test_update_oxum(self):
    bagit.make_bag(self.tmpdir)
    bag = update_bag.Repairable_Bag(self.tmpdir)
    bag.info['Payload-Oxum'] = '0.0'
    self.assertFalse(bag.is_valid())
    bag.update_baginfo()
    updated_bag = update_bag.Repairable_Bag(self.tmpdir)
    self.assertTrue(self.validate(updated_bag))
    self.assertTrue("Most-Recent-Update-Date" in updated_bag.info.keys())

  def test_bag_update_msg(self):
    bagit.make_bag(self.tmpdir)
    bag = update_bag.Repairable_Bag(self.tmpdir)
    test_message =  "How did this get here? I'm not good with computers."
    bag.update_baginfo(message = test_message)
    updated_bag = update_bag.Repairable_Bag(self.tmpdir)
    self.assertTrue(self.validate(updated_bag))
    self.assertTrue(test_message in updated_bag.info.values())

  def test_payload_file_not_in_manifest(self):
    bagit.make_bag(self.tmpdir)
    bag = update_bag.Repairable_Bag(self.tmpdir)
    f = j(self.tmpdir, "data/._.SYSTEMFILE.db\r")
    with open(f, 'w'):
      self.assertEqual(list(bag.payload_files_not_in_manifest()), ['data/._.SYSTEMFILE.db\r'])

  def test_add_payload_file_not_in_manifest(self):
    bagit.make_bag(self.tmpdir)
    bag = update_bag.Repairable_Bag(self.tmpdir)
    f = j(self.tmpdir, "data/._.SYSTEMFILE.db\r")
    with open(f, 'w') as r:
      r.write('♡')
    bag.add_payload_files_not_in_manifest()
    updated_bag = update_bag.Repairable_Bag(self.tmpdir)
    self.assertTrue(self.validate(updated_bag))

  def test_add_payload_file_not_in_multiple_manifests(self):
    bagit.make_bag(self.tmpdir, checksum=['sha1', 'sha256'])
    bag = update_bag.Repairable_Bag(self.tmpdir)
    f = j(self.tmpdir, "data/._.SYSTEMFILE.db\r")
    with open(f, 'w') as r:
      r.write('♡')
    bag.add_payload_files_not_in_manifest()
    updated_bag = update_bag.Repairable_Bag(self.tmpdir)
    self.assertTrue(self.validate(updated_bag))

  def test_delete_payload_files_not_in_manifest(self):
    bagit.make_bag(self.tmpdir)
    bag = update_bag.Repairable_Bag(self.tmpdir)
    f = j(self.tmpdir, "data/._.SYSTEMFILE.db\r")
    with open(f, 'w') as r:
      r.write('♡')
    self.assertEqual(list(bag.payload_files_not_in_manifest()), ['data/._.SYSTEMFILE.db\r'])
    bag.delete_payload_files_not_in_manifest()
    updated_bag = update_bag.Repairable_Bag(self.tmpdir)
    self.assertTrue(self.validate(updated_bag))

  def test_delete_payload_files_not_in_manifest_with_rules(self):
    bagit.make_bag(self.tmpdir)
    bag = update_bag.Repairable_Bag(self.tmpdir)
    f = j(self.tmpdir, "data/Thumbs.db")
    with open(f, 'w') as r:
      r.write('♡')
    self.assertEqual(list(bag.payload_files_not_in_manifest()), ['data/Thumbs.db'])
    bag.delete_payload_files_not_in_manifest(rules = {"Thumbs.db": {"regex": r"[Tt]humbs\\.db$", "match": False}})
    updated_bag = update_bag.Repairable_Bag(self.tmpdir)
    self.assertTrue(updated_bag.is_valid(fast = True))

  def test_do_not_delete_payload_files_not_in_manifest_not_rules(self):
    bagit.make_bag(self.tmpdir)
    bag = update_bag.Repairable_Bag(self.tmpdir)
    f = j(self.tmpdir, "data/._.SYSTEMFILE.db\r")
    with open(f, 'w') as r:
      r.write('♡')
    self.assertEqual(list(bag.payload_files_not_in_manifest()), ['data/._.SYSTEMFILE.db\r'])
    bag.delete_payload_files_not_in_manifest(rules = {"Thumbs.db": {"regex": r"[Tt]humbs\\.db$", "match": False}})
    updated_bag = update_bag.Repairable_Bag(self.tmpdir)
    self.assertEqual(list(bag.payload_files_not_in_manifest()), ['data/._.SYSTEMFILE.db\r'])


class TestMultiprocessValidation(TestSingleProcessValidation):

    def validate(self, bag, *args, **kwargs):
        return super(TestMultiprocessValidation, self).validate(bag, *args, processes=2, **kwargs)


if __name__ == '__main__':
  unittest.main()