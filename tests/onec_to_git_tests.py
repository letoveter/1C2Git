import onec_to_git
import os
import shutil




class TestDots2folders:

    def make_new_dir(self,dir_name):
        #не работает
        new_dir = os.path.abspath(os.path.curdir)+'\\'+dir_name
        os.mkdir(new_dir)
        print('make '+new_dir)
        return new_dir

    def setUp(self):
        global source_dir #поизящней сделать
        global dest_dir

        onec_to_git.parameters['how_to_copy'] = 'dummy'

        source_dir =os.path.abspath(os.path.curdir)+'\\'+'source'
        os.mkdir(source_dir)
        print('make '+source_dir)

        dest_dir = os.path.abspath(os.path.curdir)+'\\'+'dest'
        os.mkdir(dest_dir)
        print('make '+dest_dir)

    def tearDown(self):
        shutil.rmtree(source_dir)
        print('deleted '+source_dir)

        shutil.rmtree(dest_dir)
        print('deleted '+dest_dir)


    def make(self,file_name, res_name):
        desired_file = dest_dir+'\\'+res_name
        with open(source_dir+'\\'+file_name,'w') as file:
           file.write('spam')
        onec_to_git.dots2folders(source_dir,dest_dir)
        text = open(desired_file).read()
        assert text == 'spam', 'wrong file text: '+text


    def testcase_one_level(self):
        self.make('dir.test.xml','dir\\test.xml')

    def testcase_no_level(self):
        self.make('test.xml','test.xml')

    def testcase_three_level(self):
        self.make('dir1.dir2.test.xml','dir1\\dir2\\test.xml')

    def testcase_txt(self):
        self.make('dir1.test.txt','dir1\\test.txt')

    def testcase_conf(self):
        self.make('Configuration.xml', 'Configuration.xml')

    def testcase_no_res(self):
        self.make('temp','temp')

    def testcase_ten_level(self):
        self.make('dir1.dir2.dir3.dir4.dir5.dir6.dir7.dir8.dir9.dir10.test.xml','dir1\\dir2\\dir3\\dir4\\dir5\\dir6\\dir7\\dir8\\dir9\\dir10\\test.xml')

