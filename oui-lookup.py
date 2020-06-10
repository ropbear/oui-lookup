#!/usr/bin/env python3

import os
import sys
import re
import cmd
import requests
import sqlite3
import hashlib

FILENAME = "oui.tmp"
DBNAME = "oui.db"
SOURCE = "http://standards.ieee.org/develop/regauth/oui/oui.txt"

class MacFinder(cmd.Cmd):
    intro = "Type ? or help for a list of commands.\n"
    if not os.path.exists(DBNAME):
        intro = "\nYou must run 'update' if a sqlite db does not exist locally.\n\n" + intro
            
    
    prompt = ":: "
    
    def do_query(self,line):
        """query <query>\n\tExecute a raw sqlite query against the db."""
        if not os.path.exists(DBNAME):
            print("[!] Database doesn't exist, run 'update' to pull data")
            return
        db = sqlite3.connect(DBNAME)
        conn = db.cursor()
        conn.execute(line)
        rows = conn.fetchall()
        for i in rows:
            print(i)
        db.close()

    def do_lookup(self, line):
        """lookup <mac-address>\n\tLook up the OUI in the IEEE db"""
        mac = parse_mac(line.strip())
        if os.path.exists(DBNAME):
            db = sqlite3.connect(DBNAME)
            conn = db.cursor()
            conn.execute("SELECT vendor FROM vendors WHERE oui LIKE '%s'" % mac)
            rows = conn.fetchall()
            for i in rows:
                print(i)
            db.close()
            return rows
        else:
            print("[!] please first run 'update' to init the db")
            return
    
    def do_update(self, line):
        """update\n\tUpdate the db from standards.ieee.org"""

        new_instance = not os.path.exists(DBNAME)

        # retrieve and store the text file
        r = requests.get(SOURCE)
        with open(FILENAME,'w') as f:
            for line in r.text:
                f.write(line)
            
        # build and init db
        db = sqlite3.connect(DBNAME)
        cur = db.cursor()

        # md5 text file and compare to old md5
        insert_md5 = False
        new_md5 = hashlib.md5(
                open(FILENAME,'rb').read()
            ).hexdigest()
        if not new_instance:
            cur.execute("SELECT md5 FROM filehash WHERE md5 LIKE '%s'" % new_md5)
            rows = cur.fetchall()
            # IF THE MD5 EXISTS IN THE FILEHASH TABLE, DON'T UPDATE
            if len(rows) > 0:
                print("[#] Already up to date")
                return
            else:
                insert_md5 = True
        else:
            insert_md5 = True
            create_vendors = "CREATE TABLE vendors(id INTEGER PRIMARY KEY, oui TEXT, vendor TEXT);"
            create_hash = "CREATE TABLE filehash(md5 TEXT PRIMARY KEY, date TEXT);"
            cur.execute(create_vendors)
            cur.execute(create_hash)

        if insert_md5:
            cur.execute("INSERT INTO filehash (`md5`) VALUES ('%s')" % new_md5)
        insert = "INSERT INTO vendors (`oui`,`vendor`) VALUES "

        # parse the text file
        vendors = parse_ieee(FILENAME)

        for tup in vendors:
            query = insert + "('%s','%s')\n" % (tup[0],tup[1].replace("'",""))
            try:
                cur.execute(query)
            except Exception as e:
                print("[!] Exception: %s" % e)
                db.close()
                sys.exit(1)
        db.commit()
        db.close()

    def do_clean(self, line):
        """clean\n\tRemove sqlite db"""
        if os.path.exists(DBNAME):
            os.remove(DBNAME)
        if os.path.exists(FILENAME):
            os.remove(FILENAME)
        return

    def do_splat(self, line):
        """splat\n\tPaste multiple lines of macs"""
        if not os.path.exists(DBNAME):
            print("[!] please first run 'update' to init the db")
            return
        ouis = {''}
        splat = sys.stdin.read()
        regex = r'([0-9A-Fa-f]{2}[.:-]?){5}([0-9A-Fa-f]{2})'
        found = 0
        for match in re.finditer(regex,splat):
            found += 1
            mac = match.group()
            oui = parse_mac(mac)
            ouis.add((oui,mac))
        ouis.remove('')
        print("\n[+] Splat results:\nFound %d things that look like macs...\n" % found)
        for tup in ouis:
            row = self.do_lookup(tup[0])
            if len(row) > 0:
                print(tup[1]+"\n")
        return ouis
        

    def do_quit(self, line):
        sys.exit(0)

    def do_exit(self, line):
        sys.exit(0)

def parse_ieee(filename):
    """
    PURPOSE: Parse txt file from IEEE and return list of mac,vendor tuples.
    """
    vendors = []
    with open(FILENAME,'r') as f:
        for line in f:
            if "(base 16)" in line:
                vendor = tuple(re.sub(
                    r"\s*([0-9a-zA-Z]+)[\s\t]*\(base 16\)[\s\t]*(.*)\n", 
                    r"\1;;\2", 
                    line).split(";;")
                )
                vendors.insert(0,vendor)
    return vendors

def parse_mac(mac):
    alnum = re.sub('[^A-Fa-f0-9]+','',mac)
    upper = alnum.upper()
    oui = upper[0:6]
    return oui

if __name__ == '__main__':
    try:
        MacFinder().cmdloop()
    except KeyboardInterrupt:
        sys.exit(1)

