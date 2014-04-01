#!/usr/local/bin/python
import sys
import xml.etree.ElementTree as etree
import pyodbc
import configparser
import os
import datetime
import glob
import shutil
import filecmp
import hashlib
import pickle

__author__ = 'jgoncharova'

parametrs = {}
meta_table_list = []
uuid_dict = {}



def read_meta_object(node, type):
    elements_list = node.findall("{http://v8.1c.ru/8.3/MDClasses}" + type)
    elements_defined_list = [{'type': type, 'name': x.text} for x in elements_list]
    meta_table_list.extend(elements_defined_list)


def read_meta_table():
    """
	считывает список метаданных из файла Configuration.xml
	на всякий случаей формируем 2 коллекции:
	словарь meta_table_dict с значениями-списками объектов метаданных
	и список meta_table_list содержащий словари
    """

    conf_xml_name = parametrs['full_text_catalog'] + '\Configuration.xml'
    conf_xml_tree = etree.parse(conf_xml_name)
    children_objects = conf_xml_tree.getroot()[0][2]

    read_meta_object(children_objects, 'Language')
    read_meta_object(children_objects, 'Subsystem')
    read_meta_object(children_objects, 'StyleItem')
    read_meta_object(children_objects, 'CommonPicture')
    read_meta_object(children_objects, 'SessionParameter')
    read_meta_object(children_objects, 'Role')
    read_meta_object(children_objects, 'CommonTemplate')
    read_meta_object(children_objects, 'FilterCriterion')
    read_meta_object(children_objects, 'CommonModule')
    read_meta_object(children_objects, 'CommonAttribute')
    read_meta_object(children_objects, 'ExchangePlan')
    read_meta_object(children_objects, 'XDTOPackage')
    read_meta_object(children_objects, 'WebService')
    read_meta_object(children_objects, 'EventSubscription')
    read_meta_object(children_objects, 'ScheduledJob')
    read_meta_object(children_objects, 'SettingsStorage')
    read_meta_object(children_objects, 'FunctionalOption')
    read_meta_object(children_objects, 'FunctionalOptionsParameter')
    read_meta_object(children_objects, 'CommonCommand')
    read_meta_object(children_objects, 'CommandGroup')
    read_meta_object(children_objects, 'Constant')
    read_meta_object(children_objects, 'CommonForm')
    read_meta_object(children_objects, 'Catalog')
    read_meta_object(children_objects, 'Document')
    read_meta_object(children_objects, 'DocumentNumerator')
    read_meta_object(children_objects, 'Sequence')
    read_meta_object(children_objects, 'DocumentJournal')
    read_meta_object(children_objects, 'Enum')
    read_meta_object(children_objects, 'Report')
    read_meta_object(children_objects, 'DataProcessor')
    read_meta_object(children_objects, 'InformationRegister')
    read_meta_object(children_objects, 'AccumulationRegister')
    read_meta_object(children_objects, 'ChartOfCharacteristicTypes')
    read_meta_object(children_objects, 'ChartOfAccounts')
    read_meta_object(children_objects, 'AccountingRegister')
    read_meta_object(children_objects, 'ChartOfCalculationTypes')

    with open('meta_table_list.dat', 'wb') as dump_file:
        pickle.dump(meta_table_list,dump_file)

def read_ini_file():
    """
	считываем файл с настройками
	файл должен называться 1C2Git.cfg и лежать рядом со сценарием 1C2Git.py
	1C2Git.cfg не коммитится!!
	"""
    config_raw = configparser.ConfigParser()
    config_raw.read('1C2Git.cfg')
    for section in config_raw.sections():
        parametrs.update(config_raw.items(section))



def read_oblect_uuid_and_dependencies(metadata_item):
    """
	считывает файл с описанием объекта метаданных
	добавляет в таблицу meta_table_list зависимые файлы с их guiduid
	"""

    this_file_name = parametrs['full_text_catalog'] + '\\' + metadata_item['type'] + '.' + metadata_item[
        'name'] + '.xml'

    file_tree = etree.parse(this_file_name)
    uuid_dict[get_file_uuid(this_file_name)] = this_file_name

    #подтягиваем формы и отчеты
    if len(file_tree.getroot()[0]) > 2:  #TODO: оформить через XPath
        children = file_tree.getroot()[0][2]

        form_elements = children.findall('{http://v8.1c.ru/8.3/MDClasses}Form')
        for form_element in form_elements:
            file_name = parametrs['full_text_catalog'] + '\\' + metadata_item['type'] + '.' + metadata_item[
                'name'] + '.Form.' + form_element.text + '.xml'
            uuid_dict[get_file_uuid(file_name)] = file_name

        template_elements = children.findall('{http://v8.1c.ru/8.3/MDClasses}Template')
        for template_element in template_elements:
            file_name = parametrs['full_text_catalog'] + '\\' + metadata_item['type'] + '.' + metadata_item[
                'name'] + '.Template.' + template_element.text + '.xml'
            uuid_dict[get_file_uuid(file_name)] = file_name

        command_elements = children.findall('{http://v8.1c.ru/8.3/MDClasses}Command')
        for command_element in command_elements:
            uuid_dict[command_element.attrib['uuid']] = this_file_name + '_command'

    # заполняем таблицу зависимостей
    dep_list=[]
    root = file_tree.getroot()
    for attribute_node in root.findall('.//{http://v8.1c.ru/8.1/data/core}Type'):
        if attribute_node.text[:3]=='cfg':
           dep_list.append(attribute_node.text[4:].replace('ref',''))
    metadata_item['dependencies']=dep_list

def get_file_uuid(file_name):
    file_tree = etree.parse(file_name)
    try:
        self_uuid = file_tree.getroot()[0].attrib['uuid']
        return self_uuid
    except:
        #print('Error uuid extract from file:',file_name) #logging
        return None


def read_all_uuid():

    # считываем корень конфигурации
    conf_xml_name = parametrs['full_text_catalog'] + '\Configuration.xml'
    file_tree = etree.parse(conf_xml_name)
    self_uuid = file_tree.getroot()[0].attrib['uuid']
    uuid_dict[self_uuid] = conf_xml_name

    #TODO: мистический блок inner info - надо с ним разобраться
    conf_inner_info = file_tree.getroot()[0][0]
    for block in conf_inner_info:
        uuid_dict[block[0].text] = conf_xml_name
        uuid_dict[block[1].text] = conf_xml_name

    # если изменены базовые блоки - перечитываем всю конфигурацию
    uuid_dict['root'] = conf_xml_name
    uuid_dict['version'] = conf_xml_name
    uuid_dict['versions'] = conf_xml_name


    # считываем зависимые блоки данных (файлы) для каждого объекта конфигурации
    for metadata_item in meta_table_list:
        read_oblect_uuid_and_dependencies(metadata_item)

    # а так же ищем затерявшиеся куски в недрах subsystem
    all_subsystem_files = glob.glob(parametrs['full_text_catalog']+'\\Subsystem.*.xml')

    for one_subsystem_file in all_subsystem_files:
        # В названии файла есть слово Subsystem не только в начале
        #Todo: попадает много ненужных файлов типа Help.xml, CommandInterface.xml
        if os.path.basename(one_subsystem_file)[9:].find('Subsystem')>0:
            file_tree = etree.parse(one_subsystem_file)
            try:
                uuid_dict[get_file_uuid(one_subsystem_file)] = one_subsystem_file
            except:
                #print(this_file_name) #TODO: в логи!'''
                pass

    with open('uuid_dict.dat','wb') as dump_file:
        pickle.dump(uuid_dict, dump_file)




def check_uuid_table():
    #ищем потерянные uuid по базе данных
    unknown_uuid = []
    connect_string = 'DRIVER={{SQL Server}};SERVER={0};DATABASE={1};UID={2};PWD={3}'.format(parametrs['server_name'],
                                                                                            parametrs['dev_database'],
                                                                                            parametrs['sql_login'],
                                                                                            parametrs['sql_pass'])
    db = pyodbc.connect(connect_string)
    cursor = db.cursor()
    cursor.execute('SELECT FileName FROM Config')
    for row in cursor.fetchall():
        short_ref = row[0][:36]
        if uuid_dict.get(short_ref, None) is None:
            unknown_uuid.append(row[0])
    cursor.close()
    db.close()

    assert len(unknown_uuid)==0,'total-'+repr(len(unknown_uuid))+', first 10-'+repr(unknown_uuid[:10])

def tell2git_im_busy(message):

    mark_filename=os.path.join(parametrs['git_work_catalog'],'1C2Git_export_status.txt')

    with open(mark_filename,'w',-1,'UTF-8') as mark_file:
        mark_file.write('Идет выгрузка из 1С в Git, время начала - '+datetime.datetime.now().strftime("%d.%m.%Y %I:%M %p")+'\n')

        if type(message)==str:
           mark_file.write(message)

        elif type(message)==list:
            mark_file.write('Состав объектов для выгрузки:')
            for m_obj in message:
                mark_file.write(m_obj)
        else:
             raise Exception("Неверный тип message")



def tell2git_im_free():

    mark_filename=os.path.join(parametrs['git_work_catalog'],'1C2Git_export_status.txt')
    os.remove(mark_filename)

def dots2folders(source_catalog,destination_catalog,files_list):
    """
    копирует файлы из source_catalog в destination_catalog
    параллельно разбивая их по папкам, так что
    C:\1C2Git_files\full_text\ChartOfCalculationTypes.Удержания.Form.ФормаСписка.Form.Module.txt
    превращается в C:\Buh_korp\ChartOfCalculationTypes\Удержания\Form\ФормаСписка\Form\Module.txt
    """
    #todo: использовать список файлов
    all_dot_files=glob.glob(source_catalog+'\\*.*')

    for dot_file in all_dot_files:
        file_parts_list = os.path.basename(dot_file).split('.')
        left_part_of_file='\\'.join(file_parts_list[:-2])
        right_part_of_file = '.'.join(file_parts_list[-2:])
        new_catalog=os.path.join(destination_catalog,left_part_of_file)
        full_new_name = os.path.join(new_catalog,right_part_of_file)

        #соединим вместе новое место назначения и левую часть названия файла, оставив только последнее имя и расширение
        if not os.path.exists(new_catalog):
            os.makedirs(new_catalog)

        # а если нет параметра?
        if parametrs['how_to_copy']=='dummy':
            shutil.copy(dot_file,full_new_name)
        elif parametrs['how_to_copy']=='cmp':
            if not os.path.exists(full_new_name) or not filecmp.cmp(dot_file,full_new_name):
                shutil.copy(dot_file,full_new_name)
                #print('копируем '+dot_file)
        elif parametrs['how_to_copy']=='hash':
            if not os.path.exists(full_new_name):
                shutil.copy(dot_file,full_new_name)
            else:
                with open(dot_file, 'rb') as f:
                    file1_hash = hashlib.sha1(f.read()).hexdigest()
                #with open(full_new_name, 'rb') as f:
                    #file2_hash = hashlib.sha1(f.read()).hexdigest()
                #if not file1_hash == file2_hash:
                    # shutil.copy(dot_file,full_new_name)
           #file_hash = hashlib.sha1(open(dot_file,'r',-1,'UTF-8').read().decode('UTF-8')).hexdigest()
            #if not os.path.exists(full_new_name) or not filecmp.cmp(dot_file,full_new_name):

        else:
            raise Exception("не заполнена настройка how_to_copy")



def fill_dummy_catalog():
    import re

    for meta_object in meta_table_list:

        object_file_name = parametrs['full_text_catalog'] \
                           + '\\' + meta_object['type'] \
                           + '.' + meta_object['name'] + '.xml'

        object_new_file_name = parametrs['dummy_text_catalog'] \
                           + '\\' + meta_object['type'] \
                           + '.' + meta_object['name'] + '.xml'
                            # не работает

        if not os.path.exists(object_new_file_name):

            file_str=open(object_file_name,'r',-1,'UTF-8').read()
            unwanted_nodes = ['ChildObjects','DefaultObjectForm','DefaultListForm','DefaultChoiceForm','RegisterRecords','Characteristics']
            string_was_changed = False
            for unwanted_node in unwanted_nodes:
                find_res = re.search('<'+unwanted_node+'>.*</'+unwanted_node+'>',file_str,re.DOTALL)  #TODO: заменить грамотной записью xml!!
                if not find_res is None:
                    file_str = file_str.replace(find_res.group(),'<'+unwanted_node+'/>')
                    string_was_changed = True

            if string_was_changed:
                data_file=open(object_new_file_name,'w',-1,'UTF-8')
                data_file.write(file_str)

def connect2db():

    connect_string = 'DRIVER={{SQL Server}};SERVER={0};DATABASE={1};UID={2};PWD={3}'.format(parametrs['server_name'],
                                                                                            parametrs['dev_database'],
                                                                                            parametrs['sql_login'],
                                                                                            parametrs['sql_pass'])

    return pyodbc.connect(connect_string)




def get_changed_blocks():
    '''
    получает из запроса к 2-м базам перечень измененных блоков
    '''

    res=[]
    db = connect2db()
    cursor = db.cursor()
    try:
        query_text = '''SELECT dev.FileName
        FROM ['''+parametrs['1c_dev_base']+'''].[dbo].[Config] as dev
        LEFT JOIN  ['''+parametrs['1c_shad_base']+'''].[dbo].[Config] as shad
        ON dev.FileName = shad.FileName
        WHERE dev.Modified <> shad.Modified
        OR shad.Modified IS NULL'''
        cursor.execute(query_text)
        res = cursor.fetchall()

    except:
        print('Error get_changed_blocks: ',query_text) #TODO(me):logging
    finally:
        db.close()

    modified_objects=[]
    not_found_objects = []
    for i in res:
        object_name=uuid_dict.get(i[0],uuid_dict.get(i[0][:36],None))
        if object_name is  None:
            not_found_objects.append(i[0])
        else:
            if not object_name in modified_objects:
                modified_objects.append(object_name)


    assert len(not_found_objects)==0,\
        'Не все объекты найдены в таблице ссылок ('+str(len(not_found_objects))+', пример: '+not_found_objects[0]+')'

    return modified_objects


def move_changed_files_to_wd():
    '''
    собирает файлы, относящиеся к измененным блокам
    и копирует их в рабочий каталог
    из каталога полных текстов
    '''
    pass

def move_dummy_objects_to_wd():
    '''
    Собирает все зависимые объекты по данным измененных
    и копирует их в рабочий каталог
    из каталога  dummy
    '''
    pass

def cat_configuration_xml():
    '''
    удаляет из узла ChildObjects файла Configuration.xml все, кроме нужных:
    измененных объектов и зависящих от них,
    копирует файл Configuration.xml в рабочий каталог
    '''
    pass

def import_1c():
    '''
    Загружает конфигурацию 1С из файлов рабочего каталога
    '''
    os.system(parametrs['1c_starter']
            +' DESIGNER /S'+parametrs['1c_server']+'\\'+parametrs['1c_shad_base']
            +' /N'+parametrs['1c_shad_login']+' /P'+parametrs['1c_shad_pass']
            +' /LoadConfigFiles'+parametrs['full_text_catalog'])

def export_1c():
    os.system(parametrs['1c_starter']
            +' DESIGNER /S'+parametrs['1c_server']+'\\'+parametrs['1c_shad_base']
            +' /N'+parametrs['1c_shad_login']+' /P'+parametrs['1c_shad_pass']
            +' /DumpConfigToFiles '+parametrs['full_text_catalog'])

def copy_changed_bloсks():
    '''

    '''

def get_changed_files_list(modified_objects):
    '''
    возвращает список измененных файлов по списку объектов
    '''

    modified_files = []
    for object_name in modified_objects:
        #работаем с именем файла без расширения
        short_name = os.path.basename(object_name)[:-4]
        modified_files.extend(glob.glob(os.path.dirname(object_name)+'\\'+short_name+'*.*'))

    return modified_files

def full_export():

    begin_time = datetime.datetime.now()

    read_ini_file()

    #пишем в папку git  файл 'я работаю'
    tell2git_im_busy('проводится полная выгрузка конфигурации')


    # полностью копируем таблицу configsave в тень
    db = connect2db()
    cursor = db.cursor()
    cursor.execute('DROP TABLE ['+parametrs['1c_shad_base']+'].[dbo].[Config]')
    query_text = '''SELECT * INTO ['''+parametrs['1c_shad_base']+'''].[dbo].[Config]
    FROM  ['''+parametrs['1c_dev_base']+'''].[dbo].[Config] '''
    cursor.execute(query_text)

    db.close()



    # запускаем 1с с командой “Выгрузить файлы”

    export_1c()

    # разбираем выгруженные файлы по папкам
    dots2folders(parametrs['full_text_catalog'],parametrs['git_work_catalog'])

    # обновляем таблицу соответствий метаданных
    read_meta_table()
    read_all_uuid()
    check_uuid_table()

    #обновляем папку стабов
    fill_dummy_catalog()

    tell2git_im_free()

    print('время выполнения сценария - ',datetime.datetime.now() - begin_time)

def save_1c():

    begin_time = datetime.datetime.now()

    read_ini_file()

    with open('meta_table_list.dat', 'rb') as dump_file:
        meta_table_list.extend(pickle.load(dump_file))

    with open('uuid_dict.dat', 'rb') as dump_file:
        uuid_dict.update(pickle.load(dump_file))

    modified_objects = get_changed_blocks()

    if parametrs['full_text_catalog']+'\\Configuration.xml' in modified_objects:
        print('Нужна полная выгрузка')
        #todo: таки нужна полная выгрузка

    modified_files = get_changed_files_list(modified_objects)

    #todo: move_changed_files_to_wd
    move_changed_files_to_wd()

    #todo:move_dummy_objects_to_wd
    move_dummy_objects_to_wd()

    #todo:cat_configuration_xml
    cat_configuration_xml()

    #import_1c()

    copy_changed_bloсks()

    #export_1c()

    dots2folders(parametrs['work_catalog'],parametrs['git_work_catalog'],modified_files)

    print('время выполнения сценария - ',datetime.datetime.now() - begin_time)

def prepare():

    begin_time = datetime.datetime.now()

    read_ini_file()

    read_meta_table()

    read_all_uuid()

    check_uuid_table()

    print('время выполнения сценария - ',datetime.datetime.now() - begin_time)

if __name__ == '__main__':
    #operation = sys.argv[1]

    #if operation == '-s':
    save_1c()

    #elif operation=='-sa':
    #full_export()








