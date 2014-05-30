#!/usr/local/bin/python
import sys
from lxml import etree
import pyodbc
import configparser
import os
import datetime
import glob
import filecmp
import hashlib
import pickle
import shutil
import re
import logging
import subprocess

__author__ = 'jgoncharova'

# main collections
parameters = {}
meta_table_list = []
uuid_dict = {}
served_classes = ['CommonModule', 'Constant', 'DataProcessor', 'Enum', 'Report', 'WebService', 'XDTOPackage',
                  'Role']  #tested
served_classes.extend(['Catalog','StyleItem'])  #testing


#-- common procs

def read_ini_file(file_name):
    """
	считываем файл с настройками
	1C2Git.cfg не коммитится!!
	"""
    config_raw = configparser.ConfigParser()
    config_raw.read(file_name, 'UTF-8')
    for section in config_raw.sections():
        for parametr in config_raw.items(section):
            if parametr[0][-4:] == 'list':
                parameters[parametr[0]] = parametr[1].split(',')
            else:
                parameters[parametr[0]] = parametr[1]

    logging.debug('Считано ' + repr(len(parameters)) + ' параметров настроек')

    if not parameters:
        log_and_raise_exc('Не смогли прочитать настройки из 1C2Git.cfg')


def get_param(param_name):
    param_value = parameters.get(param_name, None)
    if param_value is None:
        log_and_raise_exc('Не найден в конфигурации параметр ' + param_name)

    return param_value


def simply_empty_dir(path):
    for the_file in os.listdir(path):
        file_path = os.path.join(path, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except:
            logging.error("can't delete " + the_file)


#reading configuration info

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
    logging.debug('========read_meta_table========')
    begin_time = datetime.datetime.now()

    conf_xml_name = parameters['full_text_catalog'] + '\Configuration.xml'
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

    logging.debug('Прочитано объектов ' + str(len(meta_table_list)))
    logging.debug('время выполнения read_meta_table - ' + str(datetime.datetime.now() - begin_time))


def read_oblect_uuid_and_dependencies(metadata_item):
    """
	считывает файл с описанием объекта метаданных
	добавляет в таблицу meta_table_list зависимые файлы с их guiduid
	"""

    this_file_name = parameters['full_text_catalog'] + '\\' + metadata_item['type'] + '.' + metadata_item[
        'name'] + '.xml'

    file_tree = etree.parse(this_file_name)
    uuid_dict[get_file_uuid(this_file_name)] = this_file_name

    #подтягиваем формы и отчеты
    root = file_tree.getroot()

    form_elements = root.findall('.//{http://v8.1c.ru/8.3/MDClasses}Form')
    for form_element in form_elements:
        file_name = parameters['full_text_catalog'] + '\\' + metadata_item['type'] + '.' + metadata_item[
            'name'] + '.Form.' + form_element.text + '.xml'
        #fixme: подумать: нужно ли хранить ссылку на файл формы, или на файл корневого объекта?
        # Или просто на объект типа Catalog.Банки?
        uuid_dict[get_file_uuid(file_name)] = file_name

    template_elements = root.findall('.//{http://v8.1c.ru/8.3/MDClasses}Template')
    for template_element in template_elements:
        file_name = parameters['full_text_catalog'] + '\\' + metadata_item['type'] + '.' + metadata_item[
            'name'] + '.Template.' + template_element.text + '.xml'
        uuid_dict[get_file_uuid(file_name)] = file_name

    command_elements = root.findall('.//{http://v8.1c.ru/8.3/MDClasses}Command')
    for command_element in command_elements:
        uuid_dict[command_element.attrib['uuid']] = this_file_name + '_command'


    # заполняем таблицу зависимостей
    dep_list = []

    #из основного описания объекта выбираем типы
    for attribute_node in root.findall('.//{http://v8.1c.ru/8.1/data/core}Type'):
        if attribute_node.text[:3] == 'cfg' and not attribute_node.text == 'cfg:' + metadata_item['type'] + 'Ref.' + \
                metadata_item['name']:
            dep_list.append(attribute_node.text[4:].replace('Ref', ''))

    #еще нам интересны ссылки из from
    for from_node in root.findall('.//*[@from]'):
        names_list = from_node.attrib['from'].split('.')
        dep_name = names_list[0] + '.' + names_list[1]
        if not dep_name in dep_list:
            dep_list.append(dep_name)

    #вытягиваем xdto пакеты из веб-сервисов
    if metadata_item['type'] == 'WebService':
        for xdto_element in [x.text for x in root.findall('.//{http://v8.1c.ru/8.3/xcf/readable}value') if
                             'XDTOPackage.' in x.text]:
            if not xdto_element in dep_list:
                dep_list.append(xdto_element)

    #вытягиваем хранилища настроек из отчетов
    if metadata_item['type'] == 'Report':
        finded_variants_storage = root.findall('.//{http://v8.1c.ru/8.3/MDClasses}VariantsStorage')
        try:
            if not finded_variants_storage is None:
                variants_storage_iterator = [x.text for x in finded_variants_storage if 'SettingsStorage.' in x.text]
                if not variants_storage_iterator is None:
                    for sstore_element in variants_storage_iterator:
                        if not sstore_element in dep_list:
                            dep_list.append(sstore_element)
        except:
            logging.error('trouble with ' + repr(metadata_item) + ', ' + repr(finded_variants_storage))


    #теперь придется перебрать все зависимые файлы и вытащить оттуда ссылки
    depended_files_list = glob.glob(
        parameters['full_text_catalog'] + '\\' + metadata_item['type'] + '.' + metadata_item[
            'name'] + '*.xml')
    for depended_file in depended_files_list:
        depended_file_tree = etree.parse(depended_file)
        depended_root = depended_file_tree.getroot()
        #Выдергиваем ссылки
        ref_list = list([x.text[4:].replace('Ref', '')
                         for x in depended_root.findall('.//{http://v8.1c.ru/8.1/data/core}Type')
                         if
                         x.text[:3] == 'cfg' and not x.text == 'cfg:' + metadata_item['type'] + 'Ref.' + metadata_item[
                             'name']])
        if not len(ref_list) == 0:
            dep_list.extend(ref_list)

        #выдергиваем роли
        role_list = list([x.attrib['name'] for x in depended_root.findall('.//*[@name]') if 'Role' in x.attrib['name']])
        if not len(role_list) == 0: dep_list.extend(role_list)

        #Функциональные опции
        fops_list = list(
            [x.text for x in depended_root.findall('.//{http://v8.1c.ru/8.3/xcf/logform}FunctionalOptions/*')])
        if not len(fops_list) == 0:
            dep_list.extend(fops_list)

        #стили
        metadata_list = list([x['type']+'.'+x['name'] for x in meta_table_list])
        #todo: может: удобно сделать глобальный список?
        with open(depended_file, 'r', -1, 'UTF-8') as opened_file:
            styles_list = list([x.replace('>style:', 'StyleItem.')[:-1]
                                for x in re.findall('>style:.*<', opened_file.read())
                                if x.replace('>style:', 'StyleItem.')[:-1] in metadata_list])

            if not len(styles_list) == 0:
                styles_list = unique_list(styles_list)
                dep_list.extend(styles_list)

    metadata_item['dependencies'] = dep_list


def get_file_uuid(file_name):
    file_tree = etree.parse(file_name)
    try:
        self_uuid = file_tree.getroot()[0].attrib['uuid']
        return self_uuid
    except:
        logging.error('Error uuid extract from file:' + repr(file_name))
        return None


def read_all_uuid():
    '''
    считывает uuid из xml-файлов, для понимания того, к какому объекту принадлежит ггшв
    filename в  таблицах config и configsave = uuid в xml-файлах
    '''

    logging.debug('========read_all_uuid========')
    begin_time = datetime.datetime.now()

    # считываем корень конфигурации
    conf_xml_name = parameters['full_text_catalog'] + '\Configuration.xml'
    file_tree = etree.parse(conf_xml_name)
    self_uuid = file_tree.getroot()[0].attrib['uuid']
    uuid_dict[self_uuid] = conf_xml_name

    #TODO: мистический блок inner info - надо с ним разобраться
    logging.debug('добавляем uuid из inner info ')
    conf_inner_info = file_tree.getroot()[0][0]
    for block in conf_inner_info:
        uuid_dict[block[0].text] = conf_xml_name
        uuid_dict[block[1].text] = conf_xml_name

    # если изменены базовые блоки - перечитываем всю конфигурацию
    uuid_dict['root'] = ''
    uuid_dict['version'] = ''
    uuid_dict['versions'] = ''


    # считываем зависимые блоки данных (файлы) для каждого объекта конфигурации
    for metadata_item in meta_table_list:
        read_oblect_uuid_and_dependencies(metadata_item)

    # а так же ищем затерявшиеся куски в недрах subsystem
    all_subsystem_files = glob.glob(parameters['full_text_catalog'] + '\\Subsystem.*.xml')

    for one_subsystem_file in all_subsystem_files:
        # В названии файла есть слово Subsystem не только в начале

        if one_subsystem_file[-8:] == 'Help.xml' or one_subsystem_file[-20:] == 'CommandInterface.xml':
            continue

        if os.path.basename(one_subsystem_file)[9:].find('Subsystem') > 0:
            file_tree = etree.parse(one_subsystem_file)
            try:
                uuid_dict[get_file_uuid(one_subsystem_file)] = one_subsystem_file
            except:
                logging.error('Не найден в get_file_uuid файл ' + repr(one_subsystem_file))

    logging.debug('размер uuid_dict-' + str(len(uuid_dict)))
    logging.debug('время выполнения read_all_uuid - ' + str(datetime.datetime.now() - begin_time))


def fill_dummy_catalog():
    logging.debug('========fill_dummy_catalog========')
    begin_time = datetime.datetime.now()
    for meta_object in meta_table_list:

        object_file_name = parameters['full_text_catalog'] \
                           + '\\' + meta_object['type'] \
                           + '.' + meta_object['name'] + '.xml'

        object_new_file_name = parameters['dummy_text_catalog'] \
                               + '\\' + meta_object['type'] \
                               + '.' + meta_object['name'] + '.xml'
        # не работает

        if not os.path.exists(object_new_file_name):

            file_str = open(object_file_name, 'r', -1, 'UTF-8').read()
            if meta_object['type'] == 'Enum':
                unwanted_nodes = []
            else:
                unwanted_nodes = [{'node': 'ChildObjects'},
                                  {'node': 'DefaultObjectForm'},
                                  {'node': 'DefaultListForm'},
                                  {'node': 'DefaultChoiceForm'},
                                  {'node': 'DefaultFolderForm'},
                                  {'node': 'DefaultFolderChoiceForm'},
                                  {'node': 'RegisterRecords'},
                                  {'node': 'Characteristics'},
                                  {'node': 'Type', 'exclude': 'StyleItem'},
                                  {'node': 'CharacteristicExtValues'},
                                  {'node': 'Location'},
                                  {'node': 'Content'}]

            for unwanted_node in unwanted_nodes:
                if not unwanted_node.get('exclude',None) is None and meta_object['type'] in unwanted_node['exclude']:
                    continue

                find_res = re.search('<' + unwanted_node['node'] + '>.*</' + unwanted_node['node'] + '>', file_str,
                                     re.DOTALL)
                if not find_res is None:
                    file_str = file_str.replace(find_res.group(), '<' + unwanted_node['node'] + '/>')

            data_file = open(object_new_file_name, 'w', -1, 'UTF-8')
            data_file.write(file_str)
    logging.debug('время выполнения fill_dummy_catalog - ' + str(datetime.datetime.now() - begin_time))


#++ talk with Git
def tell2git_im_busy(message):
    mark_filename = os.path.join(parameters['git_work_catalog'], '1C2Git_export_status.txt')

    with open(mark_filename, 'w', -1, 'UTF-8') as mark_file:
        mark_file.write(
            'Идет выгрузка из 1С в Git, время начала - ' + datetime.datetime.now().strftime("%d.%m.%Y %I:%M %p") + '\n')

        if type(message) == str:
            mark_file.write(message)

        elif type(message) == list:
            mark_file.write('Состав объектов для выгрузки:')
            for m_obj in message:
                mark_file.write(m_obj + ' ')
        else:
            raise Exception("Неверный тип message")


def tell2git_im_free():
    mark_filename = os.path.join(parameters['git_work_catalog'], '1C2Git_export_status.txt')
    try:
        os.remove(mark_filename)
        logging.debug('removed ' + mark_filename)
    except:
        logging.error('can not remove ' + mark_filename)


#++ work with db

def log_and_raise_exc(exception_text):
    logging.error(exception_text)
    raise Exception(exception_text)


def run_sql(db, cursor, query_text, check_result=False):
    try:
        res = cursor.execute(query_text)
        logging.debug('RUN ' + query_text + '\n Result:' + repr(res.rowcount) + ' rows')
    except:
        db.close()
        log_and_raise_exc('ERROR IN ' + query_text)

    if check_result and res.rowcount == -1:
        db.close()
        log_and_raise_exc('ERROR IN ' + query_text)


def copy_config():
    logging.debug('========copy_config========')
    begin_time = datetime.datetime.now()

    db = connect2db()
    cursor = db.cursor()

    query_text = 'DELETE FROM [' + parameters['1c_shad_base'] + '].[dbo].[Config]'
    run_sql(db, cursor, query_text, True)

    query_text = 'DELETE FROM [' + parameters['1c_shad_base'] + '].[dbo].[ConfigSave]'
    run_sql(db, cursor, query_text)

    query_text = '''INSERT INTO [''' + parameters['1c_shad_base'] + '''].[dbo].[Config]([FileName]
                              ,[Creation]
                              ,[Modified]
                              ,[Attributes]
                              ,[DataSize]
                              ,[BinaryData]
                              ,[PartNo])
                    SELECT [FileName]
                              ,[Creation]
                              ,[Modified]
                              ,[Attributes]
                              ,[DataSize]
                              ,[BinaryData]
                              ,[PartNo]
                    FROM [''' + parameters['1c_dev_base'] + '''].[dbo].[Config] '''
    run_sql(db, cursor, query_text, True)

    db.commit()
    db.close()
    logging.debug('время выполнения copy_config - ' + str(datetime.datetime.now() - begin_time))


def check_and_save_uuid_table():
    #ищем потерянные uuid по базе данных
    unknown_uuid = []
    connect_string = 'DRIVER={{SQL Server}};SERVER={0};DATABASE={1};UID={2};PWD={3}'.format(parameters['server_name'],
                                                                                            parameters['dev_database'],
                                                                                            parameters['sql_login'],
                                                                                            parameters['sql_pass'])
    db = pyodbc.connect(connect_string)
    cursor = db.cursor()
    cursor.execute('SELECT FileName FROM Config')
    for row in cursor.fetchall():
        short_ref = row[0][:36]
        if uuid_dict.get(short_ref, None) is None:
            unknown_uuid.append(row[0])
    cursor.close()
    db.close()

    with open(parameters['dumps_catalog'] + '\\uuid_dict.dat', 'wb') as dump_file:
        pickle.dump(uuid_dict, dump_file)

    with open(parameters['dumps_catalog'] + '\\meta_table_list.dat', 'wb') as dump_file:
        pickle.dump(meta_table_list, dump_file)

    if not len(unknown_uuid) == 0:
        log_and_raise_exc('total-' + repr(len(unknown_uuid)) + ', first 10-' + repr(unknown_uuid[:10]))


def connect2db():
    connect_string = 'DRIVER={{SQL Server}};SERVER={0};DATABASE={1};UID={2};PWD={3}'.format(parameters['server_name'],
                                                                                            parameters['dev_database'],
                                                                                            parameters['sql_login'],
                                                                                            parameters['sql_pass'])

    return pyodbc.connect(connect_string)


def get_changed_blocks():
    '''
    получает из запроса к 2-м базам перечень измененных блоков
    '''
    logging.debug('========get_changed_blocks========')

    res = []
    db = connect2db()
    cursor = db.cursor()
    try:
        query_text = '''SELECT dev.FileName
        FROM [''' + parameters['1c_dev_base'] + '''].[dbo].[Config] as dev
        LEFT JOIN  [''' + parameters['1c_shad_base'] + '''].[dbo].[Config] as shad
        ON dev.FileName = shad.FileName
        AND dev.PartNo = shad.PartNo
        WHERE dev.Modified <> shad.Modified
        OR shad.Modified IS NULL'''
        cursor.execute(query_text)
        res = cursor.fetchall()

    except:
        logging.error('Error get_changed_blocks: ', query_text)
    finally:
        db.close()

    logging.debug('find blocks-' + str(len(res)) + 'type- ' + repr(type(res)))
    return [x[0] for x in res]


def copy_changed_bloсks(source_table, dest_table, modified_blocks, use_like=False):
    '''
    копирует измененные блоки данных из dev в shad
    '''
    logging.debug('========copy_changed_bloсks========')

    res = []
    db = connect2db()
    cursor = db.cursor()

    if use_like:
        logging.debug(repr(modified_blocks))
        str_condition = 'or'.join([" (FileName LIKE \'"+x+"%\') " for x in modified_blocks if not x is None])
    else:
        str_condition = "FileName IN (\'" + "\',\'".join(modified_blocks) + "\')"

    logging.debug('changed blocks: '+repr(str_condition))
    delete_text = 'DELETE FROM ' + dest_table + ' WHERE ' + str_condition
    insert_text = '''INSERT INTO ''' + dest_table + '''
                            ([FileName]
                              ,[Creation]
                              ,[Modified]
                              ,[Attributes]
                              ,[DataSize]
                              ,[BinaryData]
                              ,[PartNo])
                    SELECT [FileName]
                              ,[Creation]
                              ,[Modified]
                              ,[Attributes]
                              ,[DataSize]
                              ,[BinaryData]
                              ,[PartNo]
                    FROM ''' + source_table + '''
                    WHERE''' + str_condition

    try:
        res = cursor.execute(delete_text)
        logging.debug('Deleted :' + repr(res.rowcount))
        res2 = cursor.execute(insert_text)
        logging.debug('Inserted :' + repr(res.rowcount))
        db.commit()
    except:
        logging.error('Delete and insert table error:')

    db.close()


def list_2SQL_list(items, var):
    sqllist = "\'" + "\',\'".join(items) + "\'"
    return sqllist


def get_changed_objects(changed_blocks):
    local_begin = datetime.datetime.now()
    modified_objects = []
    not_found_objects = []
    for i in changed_blocks:
        object_name = uuid_dict.get(i, uuid_dict.get(i[:36], None))
        if object_name is None:
            not_found_objects.append(i)
        elif object_name == '':
            pass  #todo: отбрасываем незначащие типа versions: проверить
        else:
            #short_object_name должен иметь вид "Type.Имя"
            short_object_name = '.'.join(os.path.basename(object_name).split('.')[:2])
            if not short_object_name in modified_objects:
                #пишем в список модифицированных объектов имя без расширения, например, Catalog.Банки
                modified_objects.append(short_object_name)
    logging.debug('modified_objects-' + str(len(modified_objects)))
    logging.debug('not_found_objects-' + str(len(not_found_objects)))

    # assert len(not_found_objects)==0,\
    #     'Не все объекты найдены в таблице ссылок ('+str(len(not_found_objects))+', пример: '+not_found_objects[0]+')'
    if not len(not_found_objects) == 0:
        logging.error('found unknown blocks. need to update uuid:' + str(len(not_found_objects)))

    logging.debug('время выполнения get_changed_blocks - ' + str(datetime.datetime.now() - local_begin))

    return modified_objects


#++ work with filesystem

def move_changed_files_to_wd(modified_files, **kargs:{}):
    '''
    собирает файлы, относящиеся к измененным блокам
    и копирует их в рабочий каталог
    из каталога полных текстов
    '''
    logging.debug('========move_changed_files_to_wd========')

    for file in modified_files:
        if kargs:
            new_file_name = file.replace(kargs['catalog']+'\\', '').replace(kargs['old_sep'],kargs['new_sep'])
        else:
            new_file_name = os.path.basename(file)

        shutil.copy(file, os.path.join(parameters['work_catalog'],new_file_name))
        logging.debug('copy ' + file + ' to ' + parameters['work_catalog']+'\\'+new_file_name)


def move_dummy_objects_to_wd(modified_objects):
    '''
    Собирает все зависимые объекты по данным измененных
    и копирует их в рабочий каталог
    из каталога  dummy
    '''
    logging.debug('========move_dummy_objects_to_wd========')
    all_dependencies = {}

    for modified_object in modified_objects:
        names_list = modified_object.split('.')

        if len(names_list) == 1:
            continue  #Configuration

        # ищем все зависимости в таблице метаданных, и если это не ссылка на самого себя - пишем в список
        for dependency in list([it['dependencies'] for it in meta_table_list if
                                (it['name'] == names_list[1] and it['type'] == names_list[0])])[
            0]:  #todo: заменить на что-то эту жесть
            try:
                if not dependency in modified_object:  #todo: сделать более грамотную систему проверки пересечений dummy и modified objects
                    all_dependencies[dependency] = None
            except:
                logging.error("error to read dependency: " + repr(dependency) + '=' + repr(modified_object))

    logging.debug('all_dependencies ' + repr(all_dependencies.keys()))
    #dependency - строка вида "Catalog.Банки"
    for dependency in all_dependencies.keys():
        # некоторые файлы придется оболванивать вручную, они будут храниться в другом каталоге, чтобы не затираться
        #пример такого файла - Catalog.НаборыДополнительныхРеквизитовИСведений
        if dependency in parameters['dummy_exceptions_list']:
            source_catalog = parameters['exceptions_text_catalog']
        else:
            source_catalog = parameters['dummy_text_catalog']

        dummy_name = dependency + '.xml'
        try:
            shutil.copy(source_catalog + '\\' + dummy_name, parameters['work_catalog'] + '\\' + dummy_name)
            logging.debug('copy ' + source_catalog + '\\' + dummy_name + ' to ' + parameters['work_catalog'])
        except:
            logging.error('fail to copy ' + source_catalog + '\\' + dummy_name + ' to ' + parameters['work_catalog'])

        #если есть файл с предопределенными элементами - копируем и его
        #todo: сделать копирование только по ссылкам
        predefined_name = parameters['full_text_catalog'] + '\\' + dummy_name.replace('.xml', '.Predefined.xml')
        if os.path.exists(predefined_name):
            predefined_new_name = predefined_name.replace(parameters['full_text_catalog'], parameters['work_catalog'])
            shutil.copy(predefined_name, predefined_new_name)
            logging.debug('copy ' + predefined_name + ' to ' + predefined_new_name)

    return all_dependencies.keys()


def move_always_included():
    logging.debug('========move_always_included========')
    for file in glob.glob(parameters['always_included_folder'] + '\\*.*'):
        shutil.copy(file, parameters['work_catalog'])


def cat_configuration_xml(modified_objects, all_dependencies):
    '''
    удаляет из узла ChildObjects файла Configuration.xml все, кроме нужных:
    измененных объектов и зависящих от них,
    копирует файл Configuration.xml в рабочий каталог
    '''

    logging.debug('========cat_configuration_xml========')

    with open(parameters['full_text_catalog'] + '\\Configuration.xml', 'r', -1, 'UTF-8') as source_file:
        file_str = source_file.read()
    find_res = re.search('<ChildObjects>.*</ChildObjects>', file_str, re.DOTALL)

    substitute_string = '<ChildObjects>\n'
    substitute_string += parameters.get('conf_always_included', '') + '\n'

    for modified_object in modified_objects:
        names_list = modified_object.split('.')
        if len(names_list) == 1:
            continue
            #Configuration

        node_type = names_list[0]
        node_text = names_list[1]
        substitute_string = substitute_string + '\t\t\t<' + node_type + '>' + node_text + '</' + node_type + '>\n'

    for dependency in all_dependencies:
        names_list = dependency.split('.')
        node_type = names_list[0].replace('Ref', '')
        node_text = names_list[1]
        string_to_add = '<' + node_type + '>' + node_text + '</' + node_type + '>'
        if not string_to_add in substitute_string:
            substitute_string += '\t\t\t' + string_to_add + '\n'

    substitute_string = substitute_string + '\t\t</ChildObjects>\n'

    file_str = file_str.replace(find_res.group(), substitute_string)

    logging.debug('replace ChildObjects with ' + substitute_string)

    unwanted_nodes = ['DefaultReportForm',
                      'DefaultReportVariantForm',
                      'DefaultReportSettingsForm',
                      'DefaultDynamicListSettingsForm',
                      'DefaultSearchForm',
                      'DefaultInterface',
                      'DefaultStyle',
                      'DefaultLanguage',
                      'DefaultRoles']
    for unwanted_node in unwanted_nodes:
        find_res = re.search('<' + unwanted_node + '>.*</' + unwanted_node + '>', file_str,
                             re.DOTALL)  #TODO: заменить грамотной записью xml!!
        if not find_res is None:
            file_str = file_str.replace(find_res.group(), '<' + unwanted_node + '/>')

    with open(parameters['work_catalog'] + '\\Configuration.xml', 'w', -1, 'UTF-8') as res_file:
        res_file.write(file_str)


def dots2folders(source_catalog, destination_catalog, files_list=None):
    """
    копирует файлы из source_catalog в destination_catalog
    параллельно разбивая их по папкам, так что
    C:\1C2Git_files\full_text\ChartOfCalculationTypes.Удержания.Form.ФормаСписка.Form.Module.txt
    превращается в C:\Buh_korp\ChartOfCalculationTypes\Удержания\Form\ФормаСписка\Form\Module.txt
    """
    logging.debug('========dots2folders========')
    logging.debug('source_catalog - ' + source_catalog + ', destination_catalog - ' + destination_catalog)
    begin_time = datetime.datetime.now()

    it_is_full_copying = files_list is None

    if it_is_full_copying:
        all_dot_files = os.listdir(source_catalog)
    else:
        all_dot_files = [os.path.basename(x) for x in files_list]

    for dot_file in all_dot_files:
        file_parts_list = dot_file.split('.')
        left_part_of_file = '\\'.join(file_parts_list[:-2])
        right_part_of_file = '.'.join(file_parts_list[-2:])
        new_catalog = os.path.join(destination_catalog, left_part_of_file)
        full_new_name = os.path.join(new_catalog, right_part_of_file)
        full_old_name = os.path.join(source_catalog, dot_file)

        #соединим вместе новое место назначения и левую часть названия файла, оставив только последнее имя и расширение
        if not os.path.exists(new_catalog):
            os.makedirs(new_catalog)
            logging.debug('created ' + new_catalog)

        #todo: а если нет параметра?
        if parameters['how_to_copy'] == 'dummy':
            shutil.copy(full_old_name, full_new_name)
            if not it_is_full_copying:
                logging.debug('Копируем из ' + full_old_name + ' в ' + full_new_name)
        elif parameters['how_to_copy'] == 'cmp':
            if not os.path.exists(full_new_name) or not filecmp.cmp(dot_file, full_new_name):
                shutil.copy(full_old_name, full_new_name)
                if not it_is_full_copying:
                    logging.debug('Копируем из ' + full_old_name + ' в ' + full_new_name)
        elif parameters['how_to_copy'] == 'hash':
            if not os.path.exists(full_new_name):
                shutil.copy(full_old_name, full_new_name)
                if not files_list == None: logging.debug('Копируем из ' + full_old_name + ' в ' + full_new_name)
            else:
                with open(dot_file, 'rb') as f:
                    #todo: доделать механизм хеширования
                    file1_hash = hashlib.sha1(f.read()).hexdigest()
                    #with open(full_new_name, 'rb') as f:
                    #file2_hash = hashlib.sha1(f.read()).hexdigest()
                    #if not file1_hash == file2_hash:
                    # shutil.copy(dot_file,full_new_name)
                    #file_hash = hashlib.sha1(open(dot_file,'r',-1,'UTF-8').read().decode('UTF-8')).hexdigest()
                    #if not os.path.exists(full_new_name) or not filecmp.cmp(dot_file,full_new_name):

        else:
            raise Exception("не заполнена настройка how_to_copy")
    logging.debug('время выполнения dots2folders - ' + str(datetime.datetime.now() - begin_time))


def folder2dots(source_catalog, destination_catalog):
    """
    копирует файлы из source_catalog в destination_catalog
    параллельно превращая иерархию папок в имя файла:
    C:\Buh_korp\ChartOfCalculationTypes\Удержания\Form\ФормаСписка\Form\Module.txt
    превращается в C:\1C2Git_files\full_text\ChartOfCalculationTypes.Удержания.Form.ФормаСписка.Form.Module.txt
    """
    logging.debug('========folder2dots========')
    logging.debug('source_catalog - ' + source_catalog + ', destination_catalog - ' + destination_catalog)
    begin_time = datetime.datetime.now()

    for root, dirs, files in os.walk(source_catalog):
        for file in files:
            if ('.git' in root
                or '.git' in file
                or 'Readme.md' in file):
                continue
            full_old_name = os.path.join(root, file)
            full_new_name = os.path.join(destination_catalog,
                                    full_old_name.replace(source_catalog+'\\', '').replace('\\', '.'))
            shutil.copy(full_old_name, full_new_name)

    logging.debug('время выполнения folder2dots - ' + str(datetime.datetime.now() - begin_time))


def copy_catalog(source_dir, destination_dir):
    logging.debug('========copy_catalog========')
    begin_time = datetime.datetime.now()

    shutil.rmtree(destination_dir)
    shutil.copytree(source_dir, destination_dir)

    logging.debug('время выполнения copy_catalog - ' + str(datetime.datetime.now() - begin_time))


def get_changed_files_list(modified_objects, catalog):
    '''
    возвращает список измененных файлов по списку объектов
    '''
    logging.debug('========get_changed_files_list========')
    begin_time = datetime.datetime.now()

    modified_files = []
    for object_name in modified_objects:
        #работаем с именем файла без расширения
        modified_files.extend(glob.glob(catalog + '\\' + object_name + '*.*'))
    logging.debug('изменено файлов ' + str(len(modified_files)))
    return modified_files


#++ work with 1C

def import_1c():
    '''
    Загружает конфигурацию 1С из файлов рабочего каталога
    '''
    logging.debug('========import_1c========')
    begin_time = datetime.datetime.now()
    logging.debug('+' + parameters['work_catalog'])
    status = os.system(parameters['1c_starter']
                       + ' DESIGNER /S' + parameters['1c_server'] + '\\' + parameters['1c_shad_base']
                       + ' /N' + parameters['1c_shad_login'] + ' /P' + parameters['1c_shad_pass']
                       + ' /LoadConfigFromFiles' + parameters['work_catalog']
                       + ' /out' + get_param('log_folder') + '\\import_log.txt')

    logging.debug('import status-' + repr(status))
    logging.debug('time of import_1c - ' + str(datetime.datetime.now() - begin_time))

    try:
        output_str = open(get_param('log_folder') + '\\import_log.txt').read()
    except:
        output_str = ''

    if status != 0:
        log_and_raise_exc('fail to import files to 1C: ' + output_str)


def export_1c():
    '''
    Выгружает конфигурацию 1С в файлы рабочего каталога
    '''
    logging.debug('========export_1c========')
    begin_time = datetime.datetime.now()
    status = os.system(parameters['1c_starter']
                       + ' DESIGNER /S' + parameters['1c_server'] + '\\' + parameters['1c_shad_base']
                       + ' /N' + parameters['1c_shad_login'] + ' /P' + parameters['1c_shad_pass']
                       + ' /DumpConfigToFiles ' + parameters['work_catalog']
                       + ' /out' + get_param('log_folder') + '\\export_log.txt')
    logging.debug('export status-' + repr(status))
    logging.debug('time of export_1c - ' + str(datetime.datetime.now() - begin_time))

    try:
        output_str = open(get_param('log_folder') + '\\export_log.txt').read()
    except:
        output_str = ''

    if status != 0:
        logging.error('fail to export files to 1C: ' + output_str)

    assert status == 0, 'fail to export files from 1C: ' + output_str


#++ main procedures
def full_import():
    """
    загружаем в 1С данные из рабочего каталога git
    """
    logging.debug('========full_import========')
    begin_time = datetime.datetime.now()

    simply_empty_dir(parameters['work_catalog'])
    folder2dots(parameters['git_work_catalog'], parameters['work_catalog'])
    import_1c()

    logging.debug('время выполнения сценария - ' + str(datetime.datetime.now() - begin_time))


def full_export():
    '''
    запускает полную выгрузку 1С в файлы
    '''
    logging.debug('========full_export========')
    begin_time = datetime.datetime.now()

    logging.debug('пишем в папку git  файл "я работаю"')
    tell2git_im_busy('проводится полная выгрузка конфигурации')

    logging.debug('полностью копируем таблицу configsave в тень')
    copy_config()

    logging.debug('запускаем 1с с командой “Выгрузить файлы”')
    export_1c()

    logging.debug('разбираем выгруженные файлы по папкам')
    dots2folders(parameters['work_catalog'], parameters['git_work_catalog'])

    logging.debug('обновляем таблицу соответствий метаданных')
    copy_catalog(parameters['work_catalog'], parameters['full_text_catalog'])

    read_meta_table()
    read_all_uuid()
    check_and_save_uuid_table()

    logging.debug('обновляем папку стабов')
    fill_dummy_catalog()

    tell2git_im_free()

    logging.debug('время выполнения сценария - ' + str(datetime.datetime.now() - begin_time))


def unique_list(our_list):
    return list({}.fromkeys(our_list).keys())


def need_full_export(modified_objects):
    if 'Configuration' in modified_objects:
        logging.debug('Configuration in modified_objects, need full export')
        return True

    modified_classes = [x.split('.')[0] for x in modified_objects]
    modified_classes_unique = unique_list(modified_classes)
    unserved_classes = [x for x in modified_classes_unique if x not in served_classes]
    if unserved_classes:
        logging.debug('userved classes: ' + repr(unserved_classes))
        return True
    else:
        return False


def save_1c():
    '''
    Сохраняет измененные объекты 1С в рабочий каталог Git
    '''
    logging.debug('========save_1c========')
    begin_time = datetime.datetime.now()

    tell2git_im_busy('проводится частичная выгрузка конфигурации')

    with open(parameters['dumps_catalog'] + '\\meta_table_list.dat', 'rb') as dump_file:
        meta_table_list.extend(pickle.load(dump_file))

    with open(parameters['dumps_catalog'] + '\\uuid_dict.dat', 'rb') as dump_file:
        uuid_dict.update(pickle.load(dump_file))

    modified_blocks = get_changed_blocks()
    modified_objects = get_changed_objects(modified_blocks)
    logging.debug('modified_blocks ' + repr(modified_blocks))
    logging.debug('modified_objects ' + repr(modified_objects))

    if len(modified_objects) == 0:
        logging.debug('nothing to export')
        tell2git_im_free()
        return

    tell2git_im_busy(modified_objects)

    if need_full_export(modified_objects):
        logging.debug('need full export')
        #full_export()
        return

    modified_files = get_changed_files_list(modified_objects, parameters['full_text_catalog'])

    logging.debug('empty folder ' + parameters['work_catalog'])
    simply_empty_dir(parameters['work_catalog'])

    #move_always_included()

    #todo: динамически делать недостающие болванки
    all_dependencies = move_dummy_objects_to_wd(modified_objects)

    move_changed_files_to_wd(modified_files)

    cat_configuration_xml(modified_objects, all_dependencies)

    import_1c()

    copy_changed_bloсks('[' + parameters['1c_dev_base'] + '].[dbo].[Config]',
                        '[' + parameters['1c_shad_base'] + '].[dbo].[ConfigSave]',
                        modified_blocks)

    export_1c()

    #Повторно получаем список файлов уже из  рабочего каталога
    modified_files = get_changed_files_list(modified_objects, parameters['work_catalog'])
    dots2folders(parameters['work_catalog'], parameters['git_work_catalog'], modified_files)

    copy_changed_bloсks('[' + parameters['1c_shad_base'] + '].[dbo].[ConfigSave]',
                        '[' + parameters['1c_shad_base'] + '].[dbo].[Config]',
                        modified_blocks) #todo: что хотел сказать художник???

    tell2git_im_free()

    logging.debug('время выполнения save_1c - ' + str(datetime.datetime.now() - begin_time))


def load_1c():
    '''
    при смене ветки в git загружает новые данные в 1С
    '''
    logging.debug('========load_1c========')
    begin_time = datetime.datetime.now()

    with open(parameters['dumps_catalog'] + '\\meta_table_list.dat', 'rb') as dump_file:
        meta_table_list.extend(pickle.load(dump_file))

    with open(parameters['dumps_catalog'] + '\\uuid_dict.dat', 'rb') as dump_file:
        uuid_dict.update(pickle.load(dump_file))


    with open(os.path.join(parameters['log_folder'],'branches.log')) as branches_log:
        last_brunch = branches_log.read()

    with open(os.path.join(parameters['git_work_catalog'],'.git', 'HEAD')) as branches_log:
        new_brunch = branches_log.read().split('\n')[0].replace('ref: refs/heads/','')

    output = subprocess.check_output(["C:\Program Files (x86)\Git\\bin\git.exe", '-C', parameters['git_work_catalog'],
                                      'diff', 'HEAD', last_brunch, '--name-only']).decode()
    logging.debug(repr(output))
    lines_list = output.split('\n')[:-1]
    logging.debug(repr(lines_list))
    modified_files = [os.path.join(parameters['git_work_catalog'],x.replace('/', '\\')) for x in lines_list]
    logging.debug('modified_files ' + repr(modified_files))

    modified_objects = unique_list(['.'.join(x.split('/')[:2]) for x in lines_list])
    logging.debug('modified_objects ' + repr(modified_objects))

    #todo: если изменен configuration.xml - полная загрузка

    if len(modified_objects) == 0:
        logging.debug('nothing to export')
        return

    depended_files = get_changed_files_list(modified_objects, parameters['full_text_catalog'])
    logging.debug('depended_files ' + repr(depended_files))

    simply_empty_dir(parameters['work_catalog'])

    #move_always_included()

    #todo:  динамический поиск зависимостей
    #todo: при необходимости - динамическая генерация болванки (dummy)
    all_dependencies = move_dummy_objects_to_wd(modified_objects)

    move_changed_files_to_wd(depended_files)
    move_changed_files_to_wd(modified_files,catalog=parameters['git_work_catalog'], old_sep='\\', new_sep='.')

    cat_configuration_xml(modified_objects, all_dependencies)

    import_1c()

    copy_changed_bloсks('[' + parameters['1c_shad_base'] + '].[dbo].[ConfigSave]',
                        '[' + parameters['1c_dev_base'] + '].[dbo].[ConfigSave]',
                        [get_file_uuid(file) for file in depended_files if file[-4:] == '.xml'],
                        True)

    #todo: перезапустить конфигуратор

    with open(os.path.join(parameters['log_folder'],'branches.log'),'w') as branches_log:
        branches_log.write(new_brunch)

    logging.debug('время выполнения load_1c - ' + str(datetime.datetime.now() - begin_time))


def run_tst_func():
    #full_export()
    #save_1c()
    #import_1c()
    logging.debug('========save_1c========')
    begin_time = datetime.datetime.now()


    #пробуем вытащить разницу из git
    # head_text = open(os.path.join(parameters['git_work_catalog'], '.git', 'HEAD')).read()
    # path_to_to_head=head_text.replace('ref: ', '').replace('\n','')
    # path_to_last_commit = os.path.join(parameters['git_work_catalog'], '.git', *path_to_to_head.split('/'))
    # last_commit_hash = open(path_to_last_commit).read()
    # print(4,last_commit_hash)
    #
    # p1 = subprocess.Popen(["echo", "Hello World!"], stdout=subprocess.PIPE)
    # output = p1.communicate()[0]
    # print(output)
    #
    #
    # # output = subprocess.check_output(['C:\Program Files (x86)\Git\\bin\git.exe', 'cat-file', '-p', 'HEAD'])
    # # output_decoded = output.decode("utf-8")
    # # print(output_decoded)

    #сравниваем sha-1 git_work и full_text - долго
    # git_work_catalog = parameters['git_work_catalog']
    # full_text_catalog = parameters['full_text_catalog']
    #
    # for root, dirs, files in os.walk(git_work_catalog):
    #     for file in files:
    #         if ('.git' in root
    #             or '.git' in file
    #             or 'README.md' in file):
    #             continue
    #         with open(os.path.join(root, file), "rb") as f:
    #             git_hash = hashlib.sha1(f.read()).hexdigest()
    #         dotted_name = os.path.join(full_text_catalog,
    #                                 os.path.join(root, file).replace(git_work_catalog+'\\', '').replace('\\', '.'))
    #         with open(os.path.join(dotted_name), "rb") as f:
    #             c_hash = hashlib.sha1(f.read()).hexdigest()
    #         if not git_hash == c_hash:
    #             print(dotted_name)


    # all_dot_files = os.listdir(parameters['full_text_catalog'])
    # cat = parameters['full_text_catalog']
    # for f in all_dot_files:
    #     with open(os.path.join(cat, f),'rb') as file:
    #         file1_hash = hashlib.sha1(file.read()).hexdigest()

    print('время выполнения run_tst_func - ' + str(datetime.datetime.now() - begin_time))


if __name__ == '__main__':
    format_string = u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s'
    file_name = os.path.join(os.path.dirname(sys.argv[2]) + '\\logs\\work_log_' + datetime.datetime.now().strftime(
        "%d_%m_%Y_%H_%M") + '.txt')
    logging.basicConfig(filename=file_name, level=logging.DEBUG, format=format_string)


    #todo: проверить что 3 аргументом идет именно *.cfg
    read_ini_file(sys.argv[2])

    if sys.argv[1] == '-t':
        run_tst_func()
    elif sys.argv[1] == '-s':  #save
        save_1c()
    elif sys.argv[1] == '-sa':  #save all
        full_export()
    elif sys.argv[1] == '-?':
        print('export from 1C to git')
        print('-s: partially export to git')
        print('-sa: full export to git')
        #print('-l: partially import to 1C')
        print('-la: full import to 1C')
        print('see logs in ' + parameters['log_folder'].replace(u'\\\\', '\\'))
    elif sys.argv[1] == '-la':  #load all
        full_import()
    elif sys.argv[1] == '-l':  #load
        load_1c()
    else:
        logging.error('wrong parameters ' + sys.argv[1:])
    








