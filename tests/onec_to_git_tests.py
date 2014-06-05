import onec_to_git
import os
import logging



class TestDots2folders:
    def setUp(self):
        #os.mkdir('source')
        print('setup')


    def testcase_one(self):
        print('test')
        assert True, 'поломали'

    def tearDown(self):
        print('teardown')


