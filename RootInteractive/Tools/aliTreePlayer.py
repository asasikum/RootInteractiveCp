import pandas as pd
import numpy as np
import urllib.request as urlopen
import pyparsing
from anytree import *
from .pandaTools import *
try:
    import ROOT
    ROOT.gSystem.Load("$ALICE_ROOT/lib/libSTAT.so")
except ImportError:
    pass
import re
import logging


def readDataFrameURL(fName, nrows=0):
    if 'http' in fName:
        line = urlopen(fName).readline().rstrip()  # get header - using root cvs convention
    else:
        line = open(fName).readline().rstrip()  # get header - using root cvs convention
    names = line.replace("/D", "").replace("/I", "").split(":")
    variables = []
    for a in names: variables.append(a.split('\t')[0])  #
    dataFrame = pd.read_csv(fName, sep='\t', index_col=False, names=variables, skiprows=1, nrows=nrows)
    return dataFrame


def SetAlias(data, column_name, formula):
    """
    :param data:            panda data frame
    :param column_name:     name of column for further query
    :param formula:         alias formula
    :return:                new panda data frame
    """
    newCol = data.eval(formula)
    out = data.assign(column=newCol)
    out = out.rename(columns={'column': column_name})
    return out


def treeToPanda(tree, variables, selection, nEntries, firstEntry, columnMask='default'):
    r"""
    Convert selected items from the tree into panda table
        TODO:
            * import fail in case of number of entries>2x10^6  (infinite loop) - to check the reason
            * use data source and aliases to enable characters forbidden in Pandas .[]() which are allowed in ROOT trees

    :param tree:            input tree
    :param variables:       ":" separated variable list
    :param selection:       tree selection ()
    :param nEntries:        number of entries to query
    :param firstEntry:      first entry to query
    :param columnMask:      mask - replace variable
    :return:                panda data frame
    """
    entries = tree.Draw(str(variables), selection, "goffpara", nEntries, firstEntry)  # query data
    columns = variables.split(":")
    # replace column names
    #    1.) pandas does not allow dots in names
    #    2.) user can specified own mask
    for i, column in enumerate(columns):
        if columnMask == 'default':
            column = column.replace(".fElements", "").replace(".fX$", "X").replace(".fY$", "Y")
        else:
            masks = columnMask.split(":")
            for mask in masks:
                column = column.replace(mask, "")
        columns[i] = column.replace(".", "_")

    ex_dict = {}
    for i, a in enumerate(columns):
        val = tree.GetVal(i)
        ex_dict[a] = np.frombuffer(val, dtype=float, count=entries)
    df = pd.DataFrame(ex_dict, columns=columns)
    initMetadata(df)
    metaData = tree.GetUserInfo().FindObject("metaTable")
    if metaData:
        for key in metaData:
            df.meta.metaData[key.GetName()] = key.GetTitle()
    return df


#  Dictionary processing

def aliasToDictionary(tree):
    """
    :param tree: input tree
    :return: dictionary of aliases
    """
    aliases = {}
    if tree.GetListOfAliases() is not None:
        for a in tree.GetListOfAliases(): aliases[a.GetName()] = a.GetTitle()
    return aliases


def __processAnyTreeBranch(branch0, parent):
    nodeF = Node(branch0.GetName(), parent=parent, ttype="branch")
    for branch in branch0.GetListOfBranches():
        __processAnyTreeBranch(branch, nodeF)


def treeToAnyTree(tree):
    r"""
    :param tree:  input TTree
    :return:  parent node of the anyTree object

    Example usage:
        see test_aliTreePlayer.py::test_AnyTree()

            >>> branchTree=treeToAnyTree(treeQA)
            >>> print(findall(branchTree, filter_=lambda node: re.match("bz", node.name)))
            >>> print(findall(branchTree, filter_=lambda node: re.match("MIP.*Warning$", node.name)))
            ==>
            (Node('/tree/bz'),)
            (Node('/tree/MIPattachSlopeA_Warning'), Node('/tree/MIPattachSlopeC_Warning'), Node('/tree/MIPattachSlope_comb2_Warning'), Node('/tree/MIPquality_Warning'))
    """
    parent = Node("",ttype="base")
    for branch in tree.GetListOfBranches():
        __processAnyTreeBranch(branch, parent)
    if tree.GetListOfAliases():
        for alias in tree.GetListOfAliases():
            Node(alias.GetName(), parent=parent, ttype="alias")
    for friend in tree.GetListOfFriends():
        treeF = tree.GetFriend(friend.GetName())
        nodeF = Node(friend.GetName(), parent=parent, ttype="branch")
        for branch in treeF.GetListOfBranches():
            __processAnyTreeBranch(branch, nodeF)
    tree.anyTree=parent
    return parent


def findSelectedBranch(anyTree, regexp, **findOption):
    """
    :param anyTree:
    :param regexp:
    :param findOption:
        * stop=None
        * maxlevel=None
        * mincount=None
        * maxcount=None
    :return:
        selected anyTree branches

    Example usage:
        >>>   test_aliTreePlayer.py::test_AnyTree()
        >>>   branchTree = treeToAnyTree(tree)
        >>> print(findSelectedBranch(branchTree, "MIP.*Warning"))
        ==> (Node('/MIPattachSlopeA_Warning'), Node('/MIPattachSlopeC_Warning'), Node('/MIPattachSlope_comb2_Warning'), Node('/MIPquality_Warning'))
    """
    options={
        "inPath":1,
        "inName":1
    }
    options.update(findOption)
    array=[]
    if options["inPath"]>0:
        array += findall(anyTree, filter_=lambda nodeF: re.match(regexp, str(nodeF.path)), **findOption)
    if options["inName"]>0:
        array += findall(anyTree, filter_=lambda nodeF: re.match(regexp, str(nodeF.name)), **findOption)
    return array

def findSelectedBranches(anyTree, include, exclude, **findOption):
    """
    :param anyTree:  anyTree or TTree
    :param include:  include array of regular expression
    :param exclude:  exclude array
    :return:  array of selected expression
    Example usage:
        >>> anyTree = treeToAnyTree(treeMap)
        >>> print("Search 0:",  findSelectedBranches(anyTree, [".*LHC15o.*Chi2.*meanG.*"], [".*ITS.*"]))
        >>> print("Search 1:",  findSelectedBranches(anyTree, [".*LHC15o.*Chi2.*meanG.*"], [".*TPC.*"]))
        >>>
        >>> Search 0: ['LHC15o_pass1.hnormChi2TPCMult_Tgl_mdEdxDist/meanG', 'LHC15o_pass1.hnormChi2TPCMult_Tgl_qPtDist/meanG']
        >>> Search 1: ['LHC15o_pass1.hnormChi2ITSMult_Tgl_mdEdxDist/meanG', 'LHC15o_pass1.hnormChi2ITSMult_Tgl_qPtDist/meanG']
    """
    if isinstance(anyTree, ROOT.TTree):
        anyTree=treeToAnyTree(anyTree)
    options={}
    options.update(findOption)
    variablesTree = []
    for selection in include:
        for var in findall(anyTree, filter_=lambda node: re.match(selection, str(node.leaves[-1]))):
            path=str(var.leaves[-1]).split("'")[1].replace("//","")
            isOK = 1
            if exclude:
                for varE in exclude:
                    if re.match(varE,path):
                        isOK = 0
                        break
            if isOK > 0:
                variablesTree.append(path)
    return variablesTree


def makeAliasAnyTree(key, aliases, parent=None):
    """
    Build recursive alias anytree

    :param key:          - start key
    :param parent:       - initial node
    :param aliases:      - alias dictionary
    :return:               anytree object
    """
    if (parent == None):
        parent = Node(key)
    theContent = pyparsing.Word(pyparsing.alphanums + ".+-=_><") | pyparsing.Suppress(',') | pyparsing.Suppress('||') | pyparsing.Suppress('&&') | pyparsing.Suppress('!')
    parents = pyparsing.nestedExpr('(', ')', content=theContent)
    res = parents.parseString("(" + aliases[key] + ")")[0]
    for subExpression in res:
        if len(subExpression) == 0: continue
        for a in subExpression:
            if a in aliases:
                newNode = Node(a, parent=parent, content=aliases[a])
                makeAliasAnyTree(a, aliases, newNode, )
            else:
                Node(a, parent=parent)
    return parent


def getAliasAnyTree(base, regexp, **findOption):
    """
    :param base:        base node
    :param regexp:      regular expression
    :param findOption:   see https://anytree.readthedocs.io/en/latest/api/anytree.search.html
    :return: liast of aliases fulfilling
    """
    return [a.name for a in findall(base, filter_=lambda node: re.match(regexp, node.name), **findOption)]


def getTreeInfo(tree):
    """
    GetTree information description

    :param tree:        input tree
    :return:
        * dictionary with tree information
            * friends
            * aliases
            * metaTable
    """
    treeInfo = {'aliases': aliasToDictionary(tree)}
    friends = treeInfo['friends'] = {}
    for a in tree.GetListOfFriends(): friends[a.GetName()] = a.GetTitle()
    metaTable = treeInfo['metaTable'] = {}
    if ROOT.TStatToolkit.GetMetadata(tree):
        table = ROOT.TStatToolkit.GetMetadata(tree)
        for a in table: metaTable[a.GetName()] = a.GetTitle()
    return treeInfo


def __parseVariableList(parserOut, varList):
    """
    :param parserOut:
    :param varList:
    :return:
    """
    for a in parserOut:
        if type(a) == pyparsing.ParseResults:
            __parseVariableList(a, varList)
            continue
        try:
            float(a)
            continue
        except ValueError:
            pass
        varList.append(a)
    return varList


def parseTreeVariables(expression, counts=None, verbose=0):
    r"""
    ParseTreeExpression and fill flat list with tree variable needed for evaluation
        * Used in  getAndTestVariableList

    :param verbose:     verbosity
    :param expression: expression to parse
    :param counts:
    :return: dictionary with pairs variable:count
        :type counts: dict

    Example usage:
        >>> parseVariables("x>1 & x>0 | y==1 |x+1>2| (x2<2) | (x1*2)<2| sin(x)<1")
        ==>
        {'sin': 1, 'x': 4, 'x1': 1, 'x2': 1, 'y': 1}
    """
    if verbose: logging.info("expression", expression)
    if counts is None:
        counts = dict()
    varList = []
    theContent = pyparsing.Word(pyparsing.alphanums + "._") | pyparsing.Suppress(',') | pyparsing.Suppress('|') | pyparsing.Suppress('&') | pyparsing.Suppress('!') \
                 | pyparsing.Suppress('>') | pyparsing.Suppress('=') | pyparsing.Suppress('+') | pyparsing.Suppress('-') | pyparsing.Suppress('<') | pyparsing.Suppress('*') \
                 | pyparsing.Suppress('*') | pyparsing.Suppress(':')
    parents = pyparsing.nestedExpr('(', ')', content=theContent)
    try:
        res = parents.parseString("(" + expression + ")")
        __parseVariableList(res, varList)
    except:
        logging.error("Oops!  That was no valid number.  Try again...", expression)
    for i in varList:
        counts[i] = counts.get(i, 0) + 1
    return counts


def getAndTestVariableList(expressions, toRemove=None, toReplace=None, tree=None, verbose=0):
    r"""
    :param verbose:
    :type toReplace: list
    :type toRemove: list
    :param expressions:      - list of expressions
    :param toRemove:         - list of regular expression to be ignored
    :param toReplace:        - list of regular expression to be replaced
    :param tree:             - tree
    :return:
        list of the trivial expression to export
            * getAndTest variable list
            * decompose expression and extract the list of variables/branches/aliases  which should be extracted from trees

    Example usage:
        * see also test_aliTreePlayer.py:test_TreeParsing()
            >>> selection="meanMIP>0&resolutionMIP>0"
            >>> varDraw="meanMIP:meanMIPele:resolutionMIP:xxx"
            >>> widgets="tab.sliders(slider.meanMIP(45,55,0.1,45,55),slider.meanMIPele(50,80,0.2,50,80), slider.resolutionMIP(0,0.15,0.01,0,0.15)),"
            >>> widgets+="tab.checkboxGlobal(slider.global_Warning(0,1,1,0,1),checkbox.global_Outlier(0)),"
            >>> widgets+="tab.checkboxMIP(slider.MIPquality_Warning(0,1,1,0,1),checkbox.MIPquality_Outlier(0), checkbox.MIPquality_PhysAcc(1))"
            >>> toRemove=["^tab\..*"]
            >>> toReplace=["^slider.","^checkbox."]
            >>>
            >>> getAndTestVariableList([selection,varDraw,widgets],toRemove,toReplace)
            ==>
            ('Not existing tree variable', 'xxx')
            {'meanMIP': 1, 'global_Warning': 1, 'MIPquality_Outlier': 1, 'resolutionMIP': 1, 'MIPquality_Warning': 1, 'global_Outlier': 1, 'time': 1, 'meanMIPele': 1, 'MIPquality_PhysAcc': 1}
    Usage:
        general - but it is used for the bokeDhraw from tree to export variables to bokeh format
    """
    if toReplace is None:
        toReplace = []
    if toRemove is None:
        toRemove = []
    counts = dict()
    for expression in expressions:
        if type(expression) == str:
            parseTreeVariables(expression, counts, verbose)
    pop_list = []
    for mask in toRemove:
        for a in counts.keys():
            if re.findall(mask, a):
                # del (counts[a])
                pop_list.append(a)
    for x in pop_list:
        counts.pop(x)

    for mask in toReplace:
        pop_list = []
        for key in counts.keys():
            if re.findall(mask, key):
                # newKey = re.sub(mask, "", key)
                pop_list.append(key)
                # counts[newKey] = counts.pop(key)
        for x in pop_list:
            newKey = re.sub(mask, "", x)
            counts[newKey] = counts.pop(x)
    pop_list = []
    if tree:
        dictionary = treeToAnyTree(tree)
        for key in counts.keys():
            if findSelectedBranch(dictionary, key + "$") == ():
                logging.info("Not existing tree variable", key)
                pop_list.append(key)
                # del (counts[key])
    for x in pop_list:
        counts.pop(x)
    return counts


def tree2Panda(tree, include, selection, **kwargs):
    r"""
    Convert selected items from the tree into panda table
    TODO:
        * to  consult with uproot
            * currently not able to work with friend trees
        * check the latest version of RDeatFrame (in AliRoot latest v16.16.00)
        * Add filter on metadata - e.g class of variables
    :param tree:            input tree
    :param include:         regular expresion array - processing Tree+Friends, branches, aliases
    :param selection:       tree selection ()
    :param kwargs:
        * exclude           exclude arrray
        * firstEntry        firt entry to enter
        * nEntries          number of entries to convert
        * column mask
    :return:                panda data frame
    """
    options={
        "exclude":[],
        "firstEntry":0,
        "nEntries":100000000,
        "columnMask": [[".fX$","_X"], [".fY$","_y"], [".fElements", ""]],
        "verbose":0
    }
    options.update(kwargs)
    anyTree = treeToAnyTree(tree)  # expand tree/aliases/variables
    variablesTree = findSelectedBranches(anyTree, include, options["exclude"])
    variables = ""

    for var in variablesTree:
        #if var.length<2: continue
        var=var.replace("/",".")
        variables += var + ":"
    variables = variables[0:-1]

    entries = tree.Draw(str(variables), selection, "goffpara", options["nEntries"], options["firstEntry"])  # query data
    columns = variables.split(":")
    for i, column in enumerate(columns):
        columns[i]=column.replace(".", "_")
    # replace column names
    #    1.) pandas does not allow dots in names
    #    2.) user can specified own column mask
    for i, column in enumerate(columns):
        for mask in options["columnMask"]:
            columns[i] = columns[i].replace(mask[0], mask[1])

    ex_dict = {}
    for i, a in enumerate(columns):
        val = tree.GetVal(i)
        ex_dict[a] = np.frombuffer(val, dtype=float, count=entries)
    df = pd.DataFrame(ex_dict, columns=columns)
    initMetadata(df)
    metaData = tree.GetUserInfo().FindObject("metaTable")
    if metaData:
        for key in metaData:
            df.meta.metaData[key.GetName()] = key.GetTitle()
    return df
