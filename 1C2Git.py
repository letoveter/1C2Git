#!/usr/local/bin/python
import sys
import xml.etree.ElementTree as etree
import pyodbc
import configparser
import os


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


def read_ini_file():
    """
	считываем файл с настройками
	файл должен называться 1C2Git.cfg и лежать рядом со сценарием 1C2Git.py
	1C2Git.cfg не коммитится!!
	"""
    config_raw = configparser.ConfigParser()
    config_raw.read('1C2Git.cfg')
    parametrs.update(config_raw.items('main'))


def read_oblect_uuid(metadata_item):
    """
	считывает файл с описанием объекта метаданных
	добавляет в таблицу meta_table_list зависимые файлы с их guiduid
	"""

    this_file_name = parametrs['full_text_catalog'] + '\\' + metadata_item['type'] + '\\' + metadata_item[
        'name'] + '.xml'

    file_tree = etree.parse(this_file_name)
    uuid_dict[get_file_uuid(this_file_name)] = this_file_name

    #подтягиваем формы и отчеты
    if len(file_tree.getroot()[0]) > 2:  #считывать дочерние объекты по номеру узла в дереве слишком грубо
        children = file_tree.getroot()[0][2]

        form_elements = children.findall('{http://v8.1c.ru/8.3/MDClasses}Form')
        for form_element in form_elements:
            file_name = parametrs['full_text_catalog'] + '\\' + metadata_item['type'] + '\\' + metadata_item[
                'name'] + '\\Form\\' + form_element.text + '.xml'
            uuid_dict[get_file_uuid(file_name)] = file_name

        template_elements = children.findall('{http://v8.1c.ru/8.3/MDClasses}Template')
        for template_element in template_elements:
            file_name = parametrs['full_text_catalog'] + '\\' + metadata_item['type'] + '\\' + metadata_item[
                'name'] + '\\Template\\' + template_element.text + '.xml'
            uuid_dict[get_file_uuid(file_name)] = file_name

        command_elements = children.findall('{http://v8.1c.ru/8.3/MDClasses}Command')
        for command_element in command_elements:
            uuid_dict[command_element.attrib['uuid']] = this_file_name + '_command'
        #осталось поискать вложенные папки в subsystem


def get_file_uuid(file_name):
    file_tree = etree.parse(file_name)
    try:
        self_uuid = file_tree.getroot()[0].attrib['uuid']
        return self_uuid
    except:
        print('Error uuid extract from file:') #logging


def read_all_uuid():

    # считываем корень конфигурации
    conf_xml_name = parametrs['full_text_catalog'] + '\Configuration.xml'
    file_tree = etree.parse(conf_xml_name)
    self_uuid = file_tree.getroot()[0].attrib['uuid']
    uuid_dict[self_uuid] = conf_xml_name

    # мистический блок inner info - надо с ним разобраться
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
        read_oblect_uuid(metadata_item)

    # а так же ищем затерявшиеся куски в недрах subsystem
    subsystems_catalog=parametrs['full_text_catalog'] + '\\Subsystem'
    for d, dirs, files in os.walk(subsystems_catalog):
        for file in files:
            if  d[-9:]=='Subsystem' and d!=subsystems_catalog:
                this_file_name = d + '\\' + file
                file_tree = etree.parse(this_file_name)
                try:
                    uuid_dict[read_object_uuid(this_file_name)] = this_file_name
                except:
                    print(this_file_name) # в логи!



def save_1c():

    read_ini_file()

    read_meta_table()

    read_all_uuid()



    #ищем потеряшек
    unknown_uuid=[]
    connect_string = 'DRIVER={{SQL Server}};SERVER={0};DATABASE={1};UID={2};PWD={3}'.format(parametrs['server_name'],parametrs['dev_database'],parametrs['dev_login'],parametrs['dev_pass'])
    db = pyodbc.connect(connect_string)
    cursor = db.cursor()
    cursor.execute('SELECT FileName FROM Config') #2 ConfigSave!!

    for row in cursor.fetchall():
        short_ref = row[0][:36]
        if uuid_dict.get(short_ref, None) is None:
            unknown_uuid.append(row[0])
    cursor.close()
    db.close()

    print(unknown_uuid)
    print(len(unknown_uuid))


if __name__ == '__main__':
    #Operation = sys.argv[1]

    #if Operation == '-s':
    save_1c()









