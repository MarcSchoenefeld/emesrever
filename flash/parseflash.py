#!/usr/bin/python
import zlib 
import sys
import struct

# MFP, minimalistic flash parser
# 2011, Marc Schoenefeld 

MAXFLASH=11

pot2=[1,2,4,8,16,32,64,128,256,512,1024,2048,4096,8192,16384,32768,65536]

tagnames={76:'SymbolClass',
          82:'DoABC',
          21:'DefineBitsJPEG2',
          90:'DefineBitsJPEG4',
          20:'DefineBitsLossless',
          36:'DefineBitsLossless2',
	      87:"DefineBinaryData",
	      12:'DoActions',
	      48:'DefineFont2',
	       7:'DefineButton',
	      34:'DefineButton2',
          39: 'DefineSprite',
          9:'SetBackgroundColor',
          43:'FrameLabel',
          65:'ScriptLimits',
          41:'tagNameObject (undoc)',
          77:'Metadata',
          69:'FileAttributes',
          1:'ShowFrame',
          28:'RemoveObject2',
          2:'DefineShape',
          22:'DefineShape2',
          32:'DefineShape3',
          56:'ExportAssets', 
          19:'SoundStreamBlock',
          26:'PlaceObject2',
          70:'PlaceObject',
          0:'End',
          10:'DefineFont', 
          13:'DefineFontInfo',
          11:'DefineText',
          78:'DefineScalingGrid',
          83:'DefineShape4',
          88:'DefineFontName',
          24:'Protect',
          86:'DefineSceneAndFrameLabelData',
          45:'SoundStreamHead2',
          75:'DefineFont3',
          73:'DefineFontAlignZones',
          33:'DefineText',
          74:'CSMTextSettings',
          8:'JPEGData',
          6:'DefineBits',
          35:'DefineBitsJPEG3',
          14:'DefineSound',
          37:'DefineEditText',
          15:'StartSound',
          89:'StartSound2',
          62:'DefineFontInfo2',
          66:'SetTabIndex', 
          59:'DoInitAcions',
          18:'SoundStreamHead',
          17:'DefineButtonSound',
          60:'DefineVideoStream',
          91:'DefineFont4',
          58:'EnableDebugger',
          64:'EnableDebugger2',
          63:'Special63 (undoc)'
      }

sfname={0:["Uncompressed",1],
        1:["ADCMP",1],
        2:["MP3",4],
        3:["Uncompressed LE",4],
        4:["Nellymoser 16khz",10],
        5:["Nellymoser 8khz",10],
        6:["Nellymoser",6],
        11:["Speex",11]}
        
CURRENTFILE="unknown"

def getTagName(tag):
	z = "unknown tag: %d" % tag 
	try:
		z = tagnames[tag]
	except:
		pass 
	return z 

def isTagKnown(tag):
	try:
		z = tagnames[tag]
	except:
		return False 
	return True 

def getTagMinVersion(tag):
	if tag==91 or tag==90:
		return 10
	if tag==82 or tag==88 or tag==89 or tag==87:
		return 9 
	if tag==86 or tag==84 or tag==83:
		return 8
	return -1

def getSFName(sformat):
	return "%s(%d)" %  (sfname[sformat][0],sfname[sformat][1])

def getStringFromArray(data,startpos):
	#print "startpos=%d" % startpos
	z=data.find('\0',startpos)
#	print "z=%d"% 
	return z+1,data[startpos:z]
	
def get8Bit(array,pos):
	return pos+1,ord(array[pos])

def get16Bit(array,pos):
	return pos+2,struct.unpack("H",array[pos:pos+2])[0]

def get32Bit(array,pos):
	return pos+4,struct.unpack("I",array[pos:pos+4])[0]

def getSoundInfo(tagdata,newpos):
	byte0=ord(tagdata[newpos])
	reserved=(byte0 & 192) >> 6
	syncstop=(byte0 & 32 ) >> 5
	syncnomultiple=(byte0 & 16 ) >> 4
	hasenvelope=(byte0 & 8 ) >> 3
	hasloops=(byte0 & 4 ) >> 2
	hasoutpoint=(byte0 & 2 ) >> 1
	hasinpoint=(byte0 & 1 )
#	print reserved
	newpos=newpos+1
	ep=[]
	envpoints=0
	inpoint=0
	outpoint=0
	loopcount=0
	if (hasinpoint):
		inpoint=struct.unpack("I",tagdata[newpos:newpos+4])[0]
		newpos=newpos+4
	if (hasoutpoint):
		outpoint=struct.unpack("I",tagdata[newpos:newpos+4])[0]
		newpos=newpos+4
	if (hasloops):
		loopcount=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
	if (hasenvelope):
		envpoints=struct.unpack("B",tagdata[newpos:newpos+1])[0]
		ep=[]
		newpos=newpos+1
		for i in range(0,envpoints):
			pos44=struct.unpack("I",tagdata[newpos:newpos+4])[0]
			newpos=newpos+4
			leftlevel=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			rightlevel=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			ep.append((pos44,leftlevel,rightlevel))
	return newpos, {'inpoint':inpoint,'outpoint':outpoint,'loopcount':loopcount,
				    'envpoints':envpoints,'ep':ep}
				    
def readZoneRecord(tagdata,newpos):
#	print "ltd=%d/%d" % (len(tagdata),newpos)
	numZoneData=struct.unpack("B",tagdata[newpos:newpos+1])[0]
#	print "nzd=%d" % (numZoneData)
	newpos=newpos+1
	zd=[]
	for i in range(0,numZoneData):
		alignment=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
		therange=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
		zd.append({'alignment':alignment,'range':therange})
	byte0=struct.unpack("B",tagdata[newpos:newpos+1])[0]
	reserved=byte0 & 252 >> 2
	zonemaskx=byte0 & 2 >> 1
	zonemasky=byte0 & 1 
	newpos=newpos+1
	zonerecord={'zonedata':zd,'reserved':reserved,'zonemasky':zonemasky,'zonemasky':zonemasky}
#	print len(tagdata),newpos,zonerecord
	return newpos,zonerecord
	
	
def parseTag(tag,tagdata,anfidx,endidx):
	#print "tag:%d" % tag
	#print "tagdata: %s " % repr(tagdata)
	
	dict={}
	tagname=""
	try:
		tagname=tagnames[tag]
	except:
		tagname="unknown tag %d " % tag
	
	if tag==76:
		numsymbols=struct.unpack("H",tagdata[0:2])[0]
		dict={"numsymbol":numsymbols}
		numpos = 2
		dictx = {}
		for i in range(0,numsymbols):
			tagnum=struct.unpack("H",tagdata[numpos:numpos+2])[0]
			numpos = numpos+2
			numpos,data=getStringFromArray(tagdata,numpos)
			#numpos=numpos+len(data)+1
			dictx.update({tagnum:data})
		dict.update({"data":dictx})
		
	elif tag==56:
		numsymbols=struct.unpack("H",tagdata[0:2])[0]
		dict={"count":numsymbols}
		numpos = 2
		dictx = {}
		for i in range(0,numsymbols):
			tagnum=struct.unpack("H",tagdata[numpos:numpos+2])[0]
			numpos = numpos+2
			numpos,data=getStringFromArray(tagdata,numpos)
			#numpos=numpos+len(data)+1
			dictx.update({tagnum:data})
		dict.update({"data":dictx})
	elif tag==82: # DoABC
		Flags= struct.unpack("I",tagdata[0:4])[0]
		dict={"flags":Flags}
		numpos = 4
		numpos,name=getStringFromArray(tagdata,numpos)
		dict.update({"name":name})
		#numpos = numpos + len(name)+1
		data=tagdata[numpos:]
		dict.update({"data":'bytecode=[%s]' % data[0:127]})
		dict.update({"fuzzrange": "%d-%d" % (anfidx+numpos,endidx)})
	elif tag==35: #DefineBitsJPEG3
		id= struct.unpack("H",tagdata[0:2])[0]
		alphaoffset= struct.unpack("I",tagdata[2:6])[0]
		numpos=6
		data=tagdata[numpos:alphaoffset+numpos]
		numpos=numpos+alphaoffset
		alphadata=tagdata[numpos:]
		dict={"id":id}
		numpos = 2
		data=tagdata[numpos:]
		type="unknown"
		if data.startswith("\xff\xd8\xff\xe0"): 
			type="jpeg"
		dict.update({"data":'imagedata=[%s,%d,%d]' % (type,len(data),len(alphadata))})
	elif tag==90: #DefineBitsJPEG4
		id= struct.unpack("H",tagdata[0:2])[0]
		alphaoffset= struct.unpack("I",tagdata[2:6])[0]
		deblockparm= struct.unpack("H",tagdata[6:8])[0]
		numpos=8
		data=tagdata[numpos:alphaoffset+numpos]
		numpos=numpos+alphaoffset
		alphadata=tagdata[numpos:]
		dict={"id":id}
		dict.update({"deblockparm":'deblockparm=[%d]' % deblockparm})
		data=tagdata[numpos:]
		type="unknown"
		if data.startswith("\xff\xd8\xff\xe0"): 
			type="jpeg"
		elif data.startswith("GIF"): 
			type="gif"
		elif data.startswith("PNG"): 
			type="png"
		dict.update({"data":'imagedata=[%s,%d,%d]' % (type,len(data),len(alphadata))})
	elif tag==21: #DefineBitsJPEG2
		id= struct.unpack("H",tagdata[0:2])[0]
		dict={"id":id}
		numpos = 2
		data=tagdata[numpos:]
		type="unknown"
		if data.startswith("\xff\xd8\xff\xe0"): 
			type="jpeg"
		dict.update({"data":'imagedata=[%s,%d]' % (type,len(data))})
	elif tag==6: #DefineBits
		id= struct.unpack("H",tagdata[0:2])[0]
		dict={"id":id}
		numpos = 2
		data=tagdata[numpos:]
		type="unknown"
		if data.startswith("\xff\xd8\xff\xe0"): 
			type="jpeg"
		dict.update({"data":'imagedata=[%s,%d]' % (type,len(data))})
	elif tag==28:
		depth= struct.unpack("H",tagdata[0:2])[0]
		dict.update({"depth":depth})
	elif tag==1 or tag==0:
		dict.update({"":""})
	elif tag==36 or tag==20:
		clrmap={36:'ALPHACOLORMAPDATA',20:'COLORMAPDATA'}
		bitmap={36:'ALPHABITMAPDATA',20:'BITMAPDATA'}
		
		id= struct.unpack("H",tagdata[0:2])[0]
		bitmapformat= struct.unpack("B",tagdata[2:3])[0]
		height= struct.unpack("H",tagdata[3:5])[0]
		width= struct.unpack("H",tagdata[5:7])[0]
		newpos = 7
		dict={"id":id,'bitmapformat':bitmapformat,'height':height,'width':width}
		if bitmapformat==3:
			bitmapColorTableSize= struct.unpack("B",tagdata[7:8])[0]
			dict.update({'bitmapColorTableSize':bitmapColorTableSize})
			newpos = newpos +1
			dict.update({'ZlibBitmapData': "%d  bytes of %s" % (len(tagdata[newpos:]),clrmap[tag])})
		elif bitmapformat==5 or bitmapformat==4:
			dict.update({'ZlibBitmapData': "%d  bytes of %s" % (len(tagdata[newpos:]),bitmap[tag])})
		dict.update({"fuzzrange": "%d-%d" % (anfidx+newpos,endidx)})
	elif tag==87:
		id= struct.unpack("H",tagdata[0:2])[0]
		reserved=struct.unpack("I",tagdata[2:6])[0]
		data=tagdata[6:]
		dict={"id":id,'reserved':reserved,'data':repr(data[0:63])}

	elif tag==39:
		id= struct.unpack("H",tagdata[0:2])[0]
		framecount=struct.unpack("H",tagdata[2:4])[0]
		dict={"spriteid":id,'framecount':framecount,'spritedata_l':tagdata[4:]}
	elif tag==9:
		#red= struct.unpack("B",tagdata[0:1])[0]
		#green= struct.unpack("B",tagdata[1:2])[0]
		#blue= struct.unpack("B",tagdata[2:3])[0]
		newpos,dict=getRGB(tagdata,0)
	elif tag==43:
		numpos,name=getStringFromArray(tagdata,0)
		dict={"name":name}
	elif tag==77:
		numpos,name=getStringFromArray(tagdata,0)
		dict={"metadata":name}
	elif tag==69:
		byte0=tagdata[0]
		reserved1=(byte0 and 1) > 0
		UseDirectBlit=(byte0 and 2) > 0
		UseGPU=(byte0 and 4) > 0
		HasMetadata=(byte0 and 8) > 0
		ActionScript3=(byte0 and 16) > 0
		reserved2=(byte0 and 96)
		useNetwork=(byte0 and 128) >0 
		reserved3=tagdata[1:4]
		dict={"reserved1":reserved1,'UseDirectBlit':UseDirectBlit,'UseGPU':UseGPU,'HasMetadata':HasMetadata,
		'ActionScript3':ActionScript3,'reserved2':reserved2,'useNetwork':useNetwork,'reserved3':reserved3}
	elif tag==65: #ScriptLimit
		MaxRecursionDepth=struct.unpack("H",tagdata[0:2])[0]
		ScriptTimeoutSeconds=struct.unpack("H",tagdata[2:4])[0]
		dict={"MaxRecursionDepth":MaxRecursionDepth,"ScriptTimeoutSeconds":ScriptTimeoutSeconds}
	elif tag==66: #SetTabIndex
		depth=struct.unpack("H",tagdata[0:2])[0]
		tabindex=struct.unpack("H",tagdata[2:4])[0]
		dict={"Depth":depth,"Tabindex":tabindex}
	elif tag==41:
		dict={"data":tagdata}
	elif tag==19:
		dict={"soundstreamdata":'%d bytes' % len(tagdata) }
	elif tag==15: #StartSound
#		print tag,len(tagdata)
		newpos=0
		soundid=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
#		newpos,soundclassname=getStringFromArray(tagdata,newpos)
		newpos,soundinfo=getSoundInfo(tagdata,newpos)
		#dict={"soundclassname":soundclassname,'soundinfo':soundinfo }
		dict={"soundid":soundid,'soundinfo':soundinfo }
	elif tag==17: #DefineButtonSound
		buttonsoundinfo0,buttonsoundinfo1,buttonsoundinfo2,buttonsoundinfo3=None,None,None,None
		newpos,buttonid=get16Bit(tagdata,0)
		newpos,buttonsoundchar0=get16Bit(tagdata,newpos)
		if buttonsoundchar0 != 0:
			newpos,buttonsoundinfo0=getSoundInfo(tagdata,newpos)
		newpos,buttonsoundchar1=get16Bit(tagdata,newpos)
		if buttonsoundchar1 != 0:
			newpos,buttonsoundinfo1=getSoundInfo(tagdata,newpos)
		newpos,buttonsoundchar2=get16Bit(tagdata,newpos)
		if buttonsoundchar2 != 0:
			newpos,buttonsoundinfo2=getSoundInfo(tagdata,newpos)
		newpos,buttonsoundchar3=get16Bit(tagdata,newpos)
		if buttonsoundchar3 != 0:
			newpos,buttonsoundinfo3=getSoundInfo(tagdata,newpos)
		dict={"buttonsoundchar0":buttonsoundchar0,"buttonsoundinfo0":buttonsoundinfo0,
		"buttonsoundchar1":buttonsoundchar1,"buttonsoundinfo1":buttonsoundinfo1,
		"buttonsoundchar2":buttonsoundchar2,"buttonsoundinfo2":buttonsoundinfo2,
		"buttonsoundchar3":buttonsoundchar3,"buttonsoundinfo3":buttonsoundinfo3
		 }
	elif tag==60: #DefineVideoStream
		newpos,characterid=get16Bit(tagdata,0)
		newpos,numframes=get16Bit(tagdata,newpos)
		newpos,width=get16Bit(tagdata,newpos)
		newpos,height=get16Bit(tagdata,newpos)
		newpos,byte0=get8Bit(tagdata,newpos)

		videoFlagsReserved = (byte0 & 240) >>4
		videoFlagsDeblocking = (byte0 & 14) >> 1
		videoFlagsSmoothing = (byte0 & 1)
		newpos,codecid=get8Bit(tagdata,newpos)
		dict={"characterid":characterid,'numframes':numframes,"width":width,'height':height,
		"videoFlagsReserved":videoFlagsReserved,'videoFlagsDeblocking':videoFlagsDeblocking,
		"videoFlagsSmoothing":videoFlagsSmoothing,'codecid':codecid}


	elif tag==89: #StartSound2
#		print tag,len(tagdata)
		newpos=0
#		soundid=struct.unpack("H",tagdata[newpos:newpos+2])[0]
#		newpos=newpos+2
		newpos,soundclassname=getStringFromArray(tagdata,newpos)
		newpos,soundinfo=getSoundInfo(tagdata,newpos)
		dict={"soundclassname":soundclassname,'soundinfo':soundinfo }
	#	dict={"soundid":soundid,'soundinfo':soundinfo }
		
	elif tag==26:
		dict={"placeobject2data":tagdata}
	elif tag==70:
		dict={"placeobject3data":tagdata}
	elif tag==64:
		reserved=struct.unpack("H",tagdata[0:2])[0]
		newpos=2
		password=getStringFromArray(tagdata,newpos)
		dict={"password":password,'reserved':reserved , 'tagdata':tagdata}
	elif tag==2:
		shapeid=struct.unpack("H",tagdata[0:2])[0]
		newbyte,newbit,rect= getRect(tagdata, 2)

		if newbit==0:
			newpos=newbyte
		else:
			newpos = newbyte+1
		
		fsarray=getFILLSTYLEARRAY(tagdata,newpos)
		dict={"shapeid":shapeid,"rect":rect,'fsarray':fsarray}
	elif tag==10:
		fontid=struct.unpack("H",tagdata[0:2])[0]
		nglyph=struct.unpack("H",tagdata[2:4])[0]/2
		newpos=2
		offsets=[]
		shapes=[]
		offstablestart=newpos
		for i in range(0,nglyph):
			offs=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			offsets.append(offs)
			newpos=newpos+2
		for i in range(0,nglyph):
			endpos=0
			try:
				endpos=offstablestart+offsets[i+1]
			except:
				endpos=len(tagdata)
			shape=tagdata[offstablestart+offsets[i]:endpos]
			shapes.append(shape)
		dict={"fontid":fontid,"offsets":offsets,"shapes":shapes}
	elif tag==62:#DefineFontInfo2
		fontid=struct.unpack("H",tagdata[0:2])[0]
		fontnamesize=struct.unpack("B",tagdata[2:3])[0]
		fontname=tagdata[3:3+fontnamesize]
		newpos=3+fontnamesize
		byte0=ord(tagdata[newpos])
		newpos=newpos+1
		fontFlagsReserved = (byte0 & 192) >>6
		fontFlagsSmallText = (byte0 & 32) >> 5 
		fontFlagsShiftJIS = (byte0 & 16 ) >> 4
		fontFlagsANSI = (byte0 & 8) >> 3
		fontFlagsItalic = (byte0 & 4) >> 2
		fontFlagsBold = (byte0  & 2) >> 1
		fontFlagsWideCodes = (byte0 &  1) 
		langcode=ord(tagdata[newpos])
		newpos=newpos+1
		codetable=[]
		if fontFlagsWideCodes==True:
			num=(len(tagdata)-newpos)/2
			for i in range(0,num):
#				print i 
#				print len(tagdata)-4
				codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
				newpos=newpos+2
				codetable.append(codeentry)
		else:
			print "WARNING, not allowed due to spec!"
			num=(len(tagdata)-newpos)
			for i in range(0,num):
				codeentry=struct.unpack("B",tagdata[newpos:newpos+1])[0]
				newpos=newpos+1
				codetable.append(codeentry)
		dict={"fontid":fontid,"fontname":fontname,"fontFlagsReserved":fontFlagsReserved, 
		"fontFlagsSmallText":fontFlagsSmallText,"fontFlagsShiftJIS":fontFlagsShiftJIS,
		"fontFlagsANSI":fontFlagsANSI,"fontFlagsItalic":fontFlagsItalic,
		"fontFlagsBold":fontFlagsBold,"fontFlagsWideCodes":fontFlagsWideCodes,
		"codetable":codetable,'langcode':langcode}
	elif tag==13: #DefineFontInfo
		fontid=struct.unpack("H",tagdata[0:2])[0]
		fontnamesize=struct.unpack("B",tagdata[2:3])[0]
		fontname=tagdata[3:3+fontnamesize]
		newpos=3+fontnamesize
		byte0=ord(tagdata[newpos])
		newpos=newpos+1
		fontFlagsReserved = (byte0 & 192) >>6
		fontFlagsSmallText = (byte0 & 32) >> 5 
		fontFlagsShiftJIS = (byte0 & 16 ) >> 4
		fontFlagsANSI = (byte0 & 8) >> 3
		fontFlagsItalic = (byte0 & 4) >> 2
		fontFlagsBold = (byte0  & 2) >> 1
		fontFlagsWideCodes = (byte0 &  1) 
		codetable=[]
		if fontFlagsWideCodes==True:
			num=(len(tagdata)-newpos)/2
			for i in range(0,num):
#				print i 
#				print len(tagdata)-4
				codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
				newpos=newpos+2
				codetable.append(codeentry)
		else:
			num=(len(tagdata)-newpos)
			for i in range(0,num):
				codeentry=struct.unpack("B",tagdata[newpos:newpos+1])[0]
				newpos=newpos+1
				codetable.append(codeentry)
			
		dict={"fontid":fontid,"fontname":fontname,"fontFlagsReserved":fontFlagsReserved, 
		"fontFlagsSmallText":fontFlagsSmallText,"fontFlagsShiftJIS":fontFlagsShiftJIS,
		"fontFlagsANSI":fontFlagsANSI,"fontFlagsItalic":fontFlagsItalic,
		"fontFlagsBold":fontFlagsBold,"fontFlagsWideCodes":fontFlagsWideCodes,
		"codetable":codetable}
	elif tag==33 or tag==11:
		charid=struct.unpack("H",tagdata[0:2])[0]
		res= getRectAligned(tagdata,2)
		newpos,rect=res
		res = getMatrixAligned(tagdata,newpos)
		newpos,matrix=res
		glyphbits=struct.unpack("B",tagdata[newpos:newpos+1])[0]
		newpos = newpos+1
		advancebits=struct.unpack("B",tagdata[newpos:newpos+1])[0]
		newpos=newpos+1
		dict={"rect":rect,"matrix":matrix,'advancebits':advancebits,'glyphbits':glyphbits}
		newpos,tr =  getTextRecords(tagdata,newpos,tag,glyphbits,advancebits)
		dict={"charid":charid,"rect":rect,"matrix":matrix,"textrecords":tr,'advancebits':advancebits,'glyphbits':glyphbits}
	elif tag==37: #DefineEditText
		charid=struct.unpack("H",tagdata[0:2])[0]
		res= getRectAligned(tagdata,2)
		newpos,rect=res
		byte0=ord(tagdata[newpos])
		newpos=newpos+1
		hastext=(byte0 & 128) >> 7
		wordwrap = (byte0 & 64) >>6
		multiline = (byte0 & 32) >>5
		password = (byte0 & 16) >>4
		readonly= (byte0 & 8) >> 3
		hastextcolor= (byte0 & 4) >> 2
		hasmaxlength= (byte0 & 2) >> 1
		hasfont = (byte0 & 1) 
		byte0=ord(tagdata[newpos])
		newpos=newpos+1
		hasfontclass=(byte0 & 128) >> 7
		autosize = (byte0 & 64) >>6
		haslayout = (byte0 & 32) >>5
		noselect = (byte0 & 16) >>4
		border= (byte0 & 8) >> 3
		wasstatic= (byte0 & 4) >> 2
		html= (byte0 & 2) >> 1
		useoutlines = (byte0 & 1)
		initialtext=""
		fontclass=""
		textheight=0
		fontid=0
		rgba={}
		maxlength=0
		align=0
		if (hasfont):
			fontid=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2	
		if (hasfontclass):
			newpos,fontclass=getStringFromArray(tagdata,newpos)
		if (hasfont):
			fontheight=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2	
		if (hastextcolor):
			numpos,rgba=getRGBA(tagdata,newpos)
		if (hasmaxlength):
			maxlength=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2	
		if (haslayout):
			align=struct.unpack("B",tagdata[newpos:newpos+1])[0]
			newpos=newpos+1
			leftmargin=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2	
			rightmargin=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2	
			indent=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2	
			leading=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2	
		newpos,varname=getStringFromArray(tagdata,newpos)
		if (hastext):
			newpos,initialtext=getStringFromArray(tagdata,newpos)

		dict={"charid":charid,"rect":rect,"fontid":fontid,"initialtext":initialtext,"varname":varname,
			'readonly':readonly,'fontclass':fontclass,'fontheight':fontheight,'textcolor':rgba,
			'maxlength':maxlength,'align':align,'leftmargin':leftmargin,'rightmargin':rightmargin,
			'indent':indent,'leading':leading}
	elif tag==34:
		buttonid=struct.unpack("H",tagdata[0:2])[0]
		byte0=ord(tagdata[2])
		reserved=byte0 & 254 >> 1
		trackasmenu=(byte0 & 1)
		newpos=3
		actionoffset=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
		characters=tagdata[newpos:newpos+actionoffset-1]
		charactersendflag=ord(tagdata[newpos+actionoffset-1:newpos+actionoffset])
		actions=tagdata[newpos+actionoffset:]
		dict={"buttonid":buttonid,"reserved":reserved,"trackasmenu":trackasmenu,"actionoffset":actionoffset,
			"characters":characters,'charactersendflag':charactersendflag,'actions':actions}		
	elif tag==7:
		buttonid=struct.unpack("H",tagdata[0:2])[0]
		newpos=2
		characters=[]
		while tagdata[newpos]!="\0":
			newpos,l = getButtonRecord(tagdata,newpos)
			characters.append(l) 
			print tagdata[newpos],l
		
		actions=tagdata[newpos:]
		
#		characters=tagdata[newpos:newpos+actionoffset-1]
		#charactersendflag=ord(tagdata[newpos+actionoffset-1:newpos+actionoffset])
		#actions=tagdata[newpos+actionoffset:]
		dict={"buttonid":buttonid,"actions":actions,"characters":characters,'actions':actions}		

	elif tag==59:#DoInitActions
		spriteid=struct.unpack("H",tagdata[0:2])[0]
		actions=tagdata[2:]
		dict={"spriteid":actions,"actions":actions}
	elif tag==12: #DoActions
		actions=tagdata
		dict={"actions":actions}
	elif tag==78:
		charid=struct.unpack("H",tagdata[0:2])[0]
		newpos,rect=getRectAligned(tagdata,2)
		dict={"charid":charid,"rect":rect}
	elif tag==83:
		charid=struct.unpack("H",tagdata[0:2])[0]
		newpos,boundshape=getRectAligned(tagdata,2)
		newpos,boundsedge=getRectAligned(tagdata,newpos)
		byte0=ord(tagdata[newpos])
		reserved=byte0 & 248 >> 3
		usesFillWindingRule=(byte0 & 4) >>2
		usesNonScalingStrokes=(byte0 & 2) >> 1
		usesScalingStrokes=(byte0 &1 ) 
		shapeinformation=tagdata[newpos+1:]
		dict={"charid":charid,"boundshape":boundshape,'boundsedge':boundsedge,
		'usesFillWindingRule':usesFillWindingRule,'usesNonScalingStrokes':usesNonScalingStrokes,
		'usesScalingStrokes':usesScalingStrokes,'shapeinformation':shapeinformation}
	elif tag==88: # DefineFontName
		fontid=struct.unpack("H",tagdata[0:2])[0]
		newpos,name=getStringFromArray(tagdata,2)
		newpos,copyright=getStringFromArray(tagdata,newpos)
		dict={"fontid":fontid,'name':name,'copyright':copyright,'tagdata':tagdata}
	elif tag==24:
		dict={'protect:':tagdata}
	elif tag==86:
		newpos,scenecount=getEncodedU32(tagdata,0)
		scenes=[]
		for i in range(0,scenecount):
			newpos,offset1=getEncodedU32(tagdata,newpos)
			name=getStringFromArray(tagdata,2)
			newpos = newpos+len(name)+1
			scenes.append([offset1,name])
		newpos,framelabelcount=getEncodedU32(tagdata,newpos)
		frames=[]
		for i in range(0,framelabelcount):
			newpos,framenum=getEncodedU32(tagdata,newpos)
			fnum=getEncodedU32(tagdata,newpos)
			flabel=getStringFromArray(tagdata,newpos)
			newpos = newpos+len(flabel)+1
			frames.append([fnum,flabel])
		dict={"scenes":scenes,'frames':frames}
	elif tag==18: #SoundStreamHead
		newpos=0
		byte0=ord(tagdata[newpos])
		reserved = (byte0 & 240) >> 4   
		playbacksoundrate = (byte0 & 12) >> 2
		playbacksoundsize = (byte0 & 2) >>1 
		playbacksoundtype  = (byte0 & 1)
		newpos=newpos+1
		byte1=ord(tagdata[newpos])
		compression = (byte1 & 240) >> 4 
		streamsoundrate = (byte1 & 12) >> 2
		streamsoundsize = (byte1 & 2) >>1 
		streamsoundtype  = (byte1 & 1) 
		newpos=newpos+1
		streamSoundSampleCount=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
		latencyseek=0
		if (compression==2): #MP3
			latencyseek=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
		dict={"byte0":byte0, "byte1":byte1,"reserved":reserved,'playbacksoundrate':playbacksoundrate,
		'playbacksoundsize':playbacksoundsize,'playbacksoundtype':playbacksoundtype,
		'compression':compression,'streamsoundrate':streamsoundrate,
		'streamsoundsize':streamsoundsize,'streamsoundtype':streamsoundtype,'streamsamplecount':
		streamSoundSampleCount,'latencyseek':latencyseek}
	elif tag==45: #SoundStreamHead2
		newpos=0
		byte0=ord(tagdata[newpos])
#		print byte0
		reserved = (byte0 & 240) >> 4   
		playbacksoundrate = (byte0 & 12) >> 2
		playbacksoundsize = (byte0 & 2) >>1 
		playbacksoundtype  = (byte0 & 1)
		newpos=newpos+1
		byte1=ord(tagdata[newpos])
		compression = (byte1 & 240) >> 4 
		streamsoundrate = (byte1 & 12) >> 2
		streamsoundsize = (byte1 & 2) >>1 
		streamsoundtype  = (byte1 & 1) 
		newpos=newpos+1
		streamSoundSampleCount=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
		latencyseek=0
		if (compression==2): #MP3
			latencyseek=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
		dict={"byte0":byte0, "byte1":byte1,"reserved":reserved,'playbacksoundrate':playbacksoundrate,
		'playbacksoundsize':playbacksoundsize,'playbacksoundtype':playbacksoundtype,
		'compression':compression,'streamsoundrate':streamsoundrate,
		'streamsoundsize':streamsoundsize,'streamsoundtype':streamsoundtype,'streamsamplecount':
		streamSoundSampleCount,'latencyseek':latencyseek}
	elif tag==14:
		newpos=0
		soundid=struct.unpack("H",tagdata[0:2])[0]
		newpos=2
		byte0=ord(tagdata[newpos])#
#		print byte0
		soundformat = (byte0 & 240) >> 4   
		soundrate = (byte0 & 12) >> 2
		soundsize = (byte0 & 2) >>1 
		soundtype  = (byte0 & 1)
		newpos=newpos+1
		samplecount=struct.unpack("I",tagdata[newpos:newpos+4])[0]
		sounddata=tagdata[newpos:]
		
		sfmeta=getSFName(soundformat)
		
		dict={"soundid":soundid,"byte0":byte0, "soundformat":soundformat,"soundmeta":sfmeta,"soundrate":soundrate,'soundsize':soundsize,
		'soundtype':soundtype , 'samplecount':samplecount,
		'sounddata':"%d bytes" % len(sounddata),'sdatarange':"%d-%d" % (anfidx+newpos,endidx)}
	elif tag==48:
		fontid=struct.unpack("H",tagdata[0:2])[0]
		newpos=2
		byte0=ord(tagdata[newpos])
		haslayout = (byte0 & 128) >> 7
		shiftjis = (byte0 & 64) >> 6
		smalltext = (byte0 & 32) >> 5
		ansi = (byte0 & 16) >> 4
		wideoffsets= (byte0 & 8) >> 3
		widecodes = (byte0 & 4) >> 2
		flagsitalics= (byte0 & 2) >> 1
		flagsbold=byte0 & 1
		newpos=newpos+1
		langcode=ord(tagdata[newpos])
		newpos=newpos+1
		fontnamesize=struct.unpack("B",tagdata[newpos:newpos+1])[0]
		newpos=newpos+1
		fontname=tagdata[newpos:newpos+fontnamesize]
		newpos=newpos+fontnamesize
		glyphcount=struct.unpack("H",tagdata[newpos:newpos+2])[0]
#		print "gl=%d" % glyphcount
		newpos=newpos+2
		offsettable=[]
		offsettablestart=newpos
		if wideoffsets==True:
#			num=(len(tagdata)-newpos)/2
			for i in range(0,glyphcount):
#				print i 
#				print len(tagdata)-4
				codeentry=struct.unpack("I",tagdata[newpos:newpos+4])[0]
				newpos=newpos+4
				offsettable.append(codeentry)
			codetableoffset=struct.unpack("I",tagdata[newpos:newpos+4])[0]
			newpos=newpos+4
	
		else:
#			num=(len(tagdata)-newpos)
			for i in range(0,glyphcount):
#				print i
				codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
				newpos=newpos+2
				offsettable.append(codeentry)
			codetableoffset=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
		shapetable=tagdata[newpos:offsettablestart+codetableoffset]
		newpos=offsettablestart+codetableoffset
		codetable=[]
		print fontname,glyphcount,widecodes,wideoffsets,offsettablestart,codetableoffset,newpos,len(tagdata)
		for i in range(0,glyphcount):
			print i
#				print i 
#				print len(tagdata)-4
			if widecodes==True:
				codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
				newpos=newpos+2
				codetable.append(codeentry)
			else:
				codeentry=struct.unpack("B",tagdata[newpos:newpos+1])[0]
				newpos=newpos+1
				codetable.append(codeentry)
				
		layoutinfo={}
		if haslayout:
			fontAscent=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			fontDescent=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			fontLeading=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			fontadvancetable=[]
			for i in range(0,glyphcount):
#				print i 
#				print len(tagdata)-4
				codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
				newpos=newpos+2
				fontadvancetable.append(codeentry)
			fontboundsTable=[]
			for i in range(0,glyphcount):
#				print i 
#				print len(tagdata)-4
				newpos,rect=getRectAligned(tagdata,newpos)
#				codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
#				newpos=newpos+2
				fontboundsTable.append(rect)
			kerningcount=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			#too:kernninginfo
			layoutinfo={'fontAscent':fontAscent,'fontDescent':fontDescent,
			'fontLeading':fontLeading,'kerningcount':kerningcount,'fontboundstable':fontboundsTable,
			'fontadvancetable':fontadvancetable}
			#todo:kerningcount
		dict={"fontid":fontid,"fontname":fontname, 
		"fontFlagsSmallText":smalltext,"fontFlagsShiftJIS":shiftjis,
		"fontFlagsANSI":ansi,"fontFlagsItalic":flagsitalics,
		"fontFlagsBold":flagsbold,"fontFlagsWideCodes":widecodes,
		"codetable":codetable,'layoutinfo':layoutinfo,'haslayout':haslayout}			
	elif tag==91:
		fontid=struct.unpack("H",tagdata[0:2])[0]
		newpos=2
		byte0=ord(tagdata[newpos])
		reserved = byte0 >> 4
		hasfontdata = (byte0 & 4) >> 2
		flagsitalics= (byte0 & 2) >> 1
		flagsbold=byte0 & 1
		newpos = newpos+1
		newpos,fontname=getStringFromArray(tagdata,newpos)
		if hasfontdata==1:
			fontdata=tagdata[newpos:]
		print fontname,byte0
		dict={"fontid":fontid,"fontname":fontname, 
		"reserved":reserved,"hasfontdata":hasfontdata,
		"fontFlagsItalic":flagsitalics,
		"fontFlagsBold":flagsbold,'fontdata':fontdata}
		
	elif tag==75:
		fontid=struct.unpack("H",tagdata[0:2])[0]
		newpos=2
		byte0=ord(tagdata[newpos])
		haslayout = (byte0 & 128) >> 7
		shiftjis = (byte0 & 64) >> 6
		smalltext = (byte0 & 32) >> 5
		ansi = (byte0 & 16) >> 4
		wideoffsets= (byte0 & 8) >> 3
		widecodes = (byte0 & 4) >> 2
		flagsitalics= (byte0 & 2) >> 1
		flagsbold=byte0 & 1
		newpos=newpos+1
		langcode=ord(tagdata[newpos])
		newpos=newpos+1
		fontnamesize=struct.unpack("B",tagdata[newpos:newpos+1])[0]
		newpos=newpos+1
		fontname=tagdata[newpos:newpos+fontnamesize]
		newpos=newpos+fontnamesize
		glyphcount=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
		offsettable=[]
		offsettablestart=newpos
		codetableoffset=0
		if wideoffsets==True:
#			num=(len(tagdata)-newpos)/2
			if glyphcount > 0:
				for i in range(0,glyphcount):
#					print i 
#					print len(tagdata)-4
					codeentry=struct.unpack("I",tagdata[newpos:newpos+4])[0]
					newpos=newpos+4
					offsettable.append(codeentry)
				codetableoffset=struct.unpack("I",tagdata[newpos:newpos+4])[0]
				newpos=newpos+4
	
		else:
#			num=(len(tagdata)-newpos)
			print glyphcount, fontname
			print newpos
			print len(tagdata)
			print repr(tagdata[newpos:newpos+2])
			if glyphcount > 0:
				for i in range(0,glyphcount):
					codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
					newpos=newpos+2
					offsettable.append(codeentry)
					print offsettable
				codetableoffset=struct.unpack("H",tagdata[newpos:newpos+2])[0]
				newpos=newpos+2
		shapetable=tagdata[newpos:offsettablestart+codetableoffset]
		newpos=offsettablestart+codetableoffset
		codetable=[]
		for i in range(0,glyphcount):
#				print i 
#				print len(tagdata)-4
			codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			codetable.append(codeentry)
		layoutinfo={}
		if haslayout:
			fontAscent=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			fontDescent=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			fontLeading=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
			fontadvancetable=[]
			for i in range(0,glyphcount):
#				print i 
#				print len(tagdata)-4
				codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
				newpos=newpos+2
				fontadvancetable.append(codeentry)
			fontboundsTable=[]
			for i in range(0,glyphcount):
#				print i 
#				print len(tagdata)-4
				newpos,rect=getRectAligned(tagdata,newpos)
#				codeentry=struct.unpack("H",tagdata[newpos:newpos+2])[0]
#				newpos=newpos+2
				fontboundsTable.append(rect)
			kerningcount=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			#too:kernninginfo
			layoutinfo={'fontAscent':fontAscent,'fontDescent':fontDescent,
			'fontLeading':fontLeading,'kerningcount':kerningcount,'fontboundstable':fontboundsTable,
			'fontadvancetable':fontadvancetable}
			#todo:kerningcount
		

		dict={"fontid":fontid,"fontname":fontname, 
		"fontFlagsSmallText":smalltext,"fontFlagsShiftJIS":shiftjis,
		"fontFlagsANSI":ansi,"fontFlagsItalic":flagsitalics,
		"fontFlagsBold":flagsbold,"fontFlagsWideCodes":widecodes,
		"codetable":codetable,'layoutinfo':layoutinfo,'haslayout':haslayout}

	elif tag==73:
		newpos=0
		fontid=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=2
		byte0=ord(tagdata[newpos])
		cSMTableHint=(byte0 & 192) >> 6
		reserved=(byte0 & 63)
		newpos=newpos+1
		zr=[]
		while newpos < len(tagdata):
			newpos,zonerecord = readZoneRecord(tagdata,newpos)
			zr.append(zonerecord)
		numglyphhere=len(zr)
		dict={"fontid":fontid,"cSMTableHint":cSMTableHint,'reserved':reserved,
		'zonetable':zr,'numglyphhere':numglyphhere}
	elif tag==74:
		newpos=0
		textid=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=2
		byte0=ord(tagdata[newpos])
		useFlashType=(byte0 & 192) >> 6
		gridFit=(byte0 & 56) >> 4
		reserved=(byte0 & 7) 
		newpos=newpos+1
		thickness=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
		sharpness=struct.unpack("H",tagdata[newpos:newpos+2])[0]
		newpos=newpos+2
		reserved=struct.unpack("B",tagdata[newpos:newpos+1])[0]
		dict={"textid":textid,"useFlashType":useFlashType,'reserved':reserved,
		'gridFit':gridFit,'thickness':thickness,'sharpness':sharpness}
	elif tag==8:
		newpos=0
		jpegdata=tagdata
		dict={"jpegdata":jpegdata}
	elif tag==63:
		newpos=0
		dict={'special63data':tagdata}
		
	return dict

def getTextRecords(arr,pos,uppertag,glyphbits,advancebits):
	textrecs=[]
	newpos =pos
	ende=False
	while not ende:
		byte0=ord(arr[newpos])
		if byte0==0:
			ende=True
			break
		textrecordtype=(byte0  & 128) >> 7  
		textstylereserved=(byte0 & (112)) >> 6
		texthasfont=(byte0 & 8) >> 3
		texthascolor=(byte0 & 4) >> 2
		texthasxoffset=(byte0 & 2) >> 1
		texthasyoffset=(byte0 & 1) 
		rgb=None
		xoffset=0
		yoffset=0
		textheight=0
		#print dict
		newpos=newpos+1
		if (texthasfont):
			fontid=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
		if (texthascolor):
			if uppertag==11:
				newpos,rgb=getRGB(arr,newpos)
			elif uppertag==33:
				newpos,rgb=getRGBA(arr,newpos)
		if (texthasxoffset):
			xoffset=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
		if (texthasyoffset):
			yoffset=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
		if (texthasfont):
			textheight=struct.unpack("H",tagdata[newpos:newpos+2])[0]
			newpos=newpos+2
		glyphcount=struct.unpack("B",tagdata[newpos:newpos+1])[0]
		dict={'rgb':rgb,'glyphcount':glyphcount,'fontid':fontid,'xoffset':xoffset,
		'yoffset':yoffset,'textheight':textheight,'texthascolor':texthascolor,
		'textrecordtype':textrecordtype,'textstylereserved':textstylereserved,
		'texthasfont':texthasfont}

		newpos=newpos+1
		startBit=0
		ge=[]
#		print glyphcount,glyphbits,advancebits
		for i in range(0,glyphcount):
#			print i 
			glyphindex, newpos, startBit = readBits(tagdata, glyphbits, newpos, startBit)
			glyphadvance, newpos, startBit = readBits(tagdata, advancebits, newpos, startBit)
			ge.append((glyphindex,glyphadvance))
#			print i
		if startBit!=0:
			newpos=newpos+1
		textrecs.append({'dict':dict,'glyphentries':ge})			
	return newpos,textrecs
		
def getRGB(array,pos):
	tagdata=array[pos:]
	red= struct.unpack("B",tagdata[0:1])[0]
	green= struct.unpack("B",tagdata[1:2])[0]
	blue= struct.unpack("B",tagdata[2:3])[0]
	return pos+3,{"r":red,'g':green,'b':blue}

def getRGBA(array,pos):
	tagdata=array[pos:]
	red= struct.unpack("B",tagdata[0:1])[0]
	green= struct.unpack("B",tagdata[1:2])[0]
	blue= struct.unpack("B",tagdata[2:3])[0]
	alpha=struct.unpack("B",tagdata[3:4])[0]
#	print "undefined yet"
#	sys.exit(-1)
	return pos+4,{"r":red,'g':green,'b':blue,'alpha':alpha}



def getButtonRecord(array,pos):
	byte0=ord(array[pos])
	hasblendmode = (byte0 & 32) >> 5
	hasfilterlist = (byte0 & 16) >> 4
	statehitlist = (byte0 & 8) >> 3
	statedown = (byte0 & 4) >> 2
	stateover = (byte0 & 2) >> 1
	stateup = (byte0 & 1) 
	charid = struct.unpack("H",array[pos+1:pos+3])[0]
	placedepth = struct.unpack("H",array[pos+3:pos+5])[0]
	x,matrix = getMatrixAligned(array,pos+5) 
	return x,{"matrix:":matrix,"charid":charid,"placedepth":placedepth}
	

def getMatrix(array,pos):
	byte0=ord(array[pos])
	hasscale = (byte0 & 128) >> 7
	startByte=pos 
	startBit = 1
	scalex=0
	scaley=0
	skew0=0
	skew1=0
	rotatebits=0
	scalebits=0
	if hasscale:
		scalebits, startByte, startBit = readBits(array, 5, startByte, startBit)
		scalex, startByte, startBit = readBits(array, scalebits, startByte, startBit)
		scaley, startByte, startBit = readBits(array, scalebits, startByte, startBit)
	hasrotate, startByte, startBit=readBits(array, 1, startByte, startBit)	
	if (hasrotate!=0):
		rotatebits, startByte, startBit = readBits(array, 5, startByte, startBit)
		skew0, startByte, startBit = readBits(array, rotatebits, startByte, startBit)
		skew1, startByte, startBit = readBits(array, rotatebits, startByte, startBit)
	translatebits, startByte, startBit = readBits(array,5 , startByte, startBit)
	translatex,startByte, startBit = readBits(array,translatebits , startByte, startBit)
	translatey,startByte, startBit = readBits(array,translatebits , startByte, startBit)
		
	return startByte,startBit,{'hasscale':hasscale,'rotatebits':rotatebits,'scalebits':scalebits,'translatebits':translatebits,'scalex':scalex,'scaley':scaley,'skew0':skew0,'skew1':skew1,'translatex':translatex,'translatey':translatey}

def getMatrixAligned(array,pos):
	(a,b,c)=getMatrix(array,pos)
	newpos=a
	if b!=0:
		newpos=newpos+1
	return (newpos,c)
	

def getRect(array, pos):
#	print repr(array)
#	print array[pos]
#	print ord(array[pos])
	nbits = ((ord(array[pos] ) >> 3) & 31)
	startByte = pos
	startBit = 5
	xmin, startByte, startBit = readBits(array, nbits, startByte, startBit)
	xmax, startByte, startBit = readBits(array, nbits, startByte, startBit)
	ymin, startByte, startBit = readBits(array, nbits, startByte, startBit)
	ymax, startByte, startBit = readBits(array, nbits, startByte, startBit)
#	print (startByte,startBit,(nbits,xmin,xmax,ymin,ymax))
	return (startByte,startBit,(nbits,xmin,xmax,ymin,ymax))
	
def getRectAligned(array,pos):
	(a,b,c)=getRect(array,pos)
	newpos=a
	if b!=0:
		newpos=newpos+1
	return (newpos,c)

def getEncodedU32(array,pos):
	val =0
	byte0=ord(array[pos])
	if (byte0<128):
		return 1,byte0
	val=byte0 and 127
	byte0=ord(array[pos+1])
	if (byte0<128):
		return 2,val+byte0*128
	val1=byte0 and 127
	val=val+val1*128
	byte0=ord(array[pos+2])
	if byte0<128:
		return 3,val + byte0*128*128
	val1=byte0 and 127
	val=val+val1*128*128
	byte0=ord(array[pos+3])
	if byte0<128:
		return 4,val + byte0*128*128*128
	val1=byte0 and 127
	val=val+val1*128*128*128
	byte0=ord(array[pos+4])
	return 5,val + byte0*128*128*128*128
		
def readBits(array, numOfBits, startByte, startBit):
	bits = 0

	for i in range(numOfBits):
#		f.seek(startByte)
		bit = (ord(array[startByte]) >> 7-startBit) & 1
		if i==0: 
			bits = bit
		else:
			bits = (bits << 1) | bit

		if startBit<7:
			startBit = startBit+1
		else:
			startBit = 0;
			startByte = startByte+1
#	print (numOfBits,bits, startByte, startBit)
	return bits, startByte, startBit;

def getFILLSTYLEARRAY(array,pos):
	arr = array[pos:]
	fscount = struct.unpack("B",arr[0:1])[0]
	fscountext =0
	newpos=1
	if fscount==255:
		fscountext=struct.unpack("H",arr[1:3])[0]
		newpos = newpos+2
	fsdata=array[newpos:]
	return {'fscount':fscount,'fscountext':fscountext,'fsdata':fsdata}
	


def uncompress(z):
	header={}
	sig=z[0]
	litw=z[1]
	lits=z[2]
	
	if litw!="W" or lits!="S" or (sig!="F" and sig!="C"):
		print "magic broken: %s " % CURRENTFILE
		sys.exit(-1)
	
	#print "magic sane"
	
	version=ord(z[3])
	
	if version <0 or version >MAXFLASH:
		print "WARNING: version broken:"+version
		# sys.exit(-1)
		
	#print "version sane: %d" % version
		
	length2=struct.unpack("I",z[4:8])[0]
	#print length2
	
	if sig=="F":
		rest= z[8:]
	elif sig == "C":
		rest = zlib.decompress(z[8:])
	newname = CURRENTFILE.replace(".swf",".unpack.swf") 
	print newname
	nn = file(newname,"wb")
	thelen=struct.pack("I",len(rest)+8)
	z='FWS'+chr(version)+thelen
	nn.write("%s%s" %  (z,rest))
	nn.close()


def getHeaderAndRest(z):
	header={}
	sig=z[0]
	litw=z[1]
	lits=z[2]
	
	if litw!="W" or lits!="S" or (sig!="F" and sig!="C"):
		print "magic broken: %s " % CURRENTFILE
		sys.exit(-1)
	
	#print "magic sane"
	
	version=ord(z[3])
	
	if version <0 or version >MAXFLASH:
		print "version broken:%d" % version
		# sys.exit(-1)
		
	#print "version sane: %d" % version
		
	length2=struct.unpack("I",z[4:8])[0]
	#print length2
	
	if sig=="F":
		rest= z[8:]
	elif sig == "C":
		rest = zlib.decompress(z[8:])
	
	res= getRect(rest,0)
	
	newbyte,newbit,rect=res
	
	if newbit==0:
		newpos=newbyte
	else:
		newpos = newbyte+1
		
	framerate1 = struct.unpack("B",rest[newpos:newpos+1])[0]
	framerate2 = struct.unpack("B",rest[newpos+1:newpos+2])[0]
	framecount = struct.unpack("H",rest[newpos+2:newpos+4])[0]
	
	framerate= str(framerate1)+":"+str(framerate2)
	#print framecount
	newpos = newpos + 4
	header.update({'currentfile':CURRENTFILE,'version':version,'compressed':sig=="C",'rect':rect,'framecount':framecount,'framerate':framerate,'length':length2})
	return (newpos,header,rest)

def getTags(rest,newpos):	
	endtag=False
#	print newpos
	tags=[]
	while not endtag and newpos < len(rest):
		start=newpos
		tagval=rest[newpos:newpos+2]
		tagx = struct.unpack("H",rest[newpos:newpos+2])[0]
		newpos = newpos+2
		val1 = int(tagx/256) 
		val2 = tagx-int(tagx/256)*256 
		
		taglen = val2 & 63 
		tag = int((tagx-taglen) / 64) 
		fuzzstart=newpos
		if taglen==63:
			if newpos > len(rest)-3:
				break
			reallen = struct.unpack("I",rest[newpos:newpos+4])[0]
			newpos = newpos+4
			taglen = reallen	 
			fuzzstart=fuzzstart+4
		
		tagdata = rest[newpos:newpos+taglen]
		
	#	parsedtagdata=parseTag(tag,tagdata)
		
	#	if parsedtagdata=="":
	#		parsedtagdata=repr(tagdata[0:64])
		
	#	print "%d:%d:%d:%s" % (newpos,tag,taglen,getTagName(tag))
		tags.append({'start':start,'tag':tag,'taglen':taglen,'fuzzstart':fuzzstart,'fuzzend':fuzzstart+len(tagdata),'tagdata':tagdata})
		
	
		newpos = newpos+taglen
	
		
		if (tag==0):
	#		print "endtag found at %d " % (newpos)
			endtag=True

	if endtag==False:
			print "[*] no endtag found for %s at %d" %  (CURRENTFILE,newpos)   
#			sys.exit(-1)

		
	return tags	

def uniqlist(list,idfun=None):
    # order preserving
    if idfun is None:
        def idfun(x): return x
    seen = {}
    result = []
    for item in list:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result
		

def usage(arg):
#TODO:Correct Opts! 
	print "parseflash.py file --action --actionarg1 .. --actionargn"
	print "abort reason: %s" %arg
	sys.exit(-1)

#TODO:GetOpt! 
if __name__=='__main__':
	
	CURRENTFILE=sys.argv[1]
	thefile= open(CURRENTFILE,"rb")
	z = thefile.read()
	(newpos,header,rest)=getHeaderAndRest(z)
	tags=getTags(rest,newpos)	
	action="--parse"
	try:
		action=sys.argv[2].lower()
	except:
		pass
	mode=""
	try:
		mode=sys.argv[3].lower()
	except:
		pass
	printlong=False
	if action=="--uncompress":
		uncompress(z)
		sys.exit(0)
	if mode=="--printlong":
		printlong=True
	if action=="--listtags":
		unknowntags=[]
		print header
		for thetag in tags:
			tag=thetag['tag']
#			if tag!=theType and theType!=-1:
#				continue
			tagdata=thetag['tagdata']
			if not isTagKnown(tag):
				unknowntags.append(tag)
			start=thetag['start']
			fa=thetag['fuzzstart']
			fe=thetag['fuzzend']
#			parsedtagdata=parseTag(tag,tagdata)
#			if parsedtagdata=="":
#				parsedtagdata=repr(tagdata[0:64])
			taglen=thetag['taglen']
			
			print "%05X:%05X:%05X:%3d:%s:%d:%s-%s" % (start,fa,fe,tag,getTagName(tag),taglen,fa,fe)
		
		if unknowntags!=[]:
			print "unknown tags detected: %s" % repr(uniqlist(unknowntags))
	if action=="--unknowntags":
		unknowntags=[]
		for thetag in tags:
			tag=thetag['tag']
			if not isTagKnown(tag):
				unknowntags.append(tag)
		
		if unknowntags!=[]:
			print "unknown tags detected: %s:%s" % (repr(uniqlist(unknowntags)),CURRENTFILE)

	elif action=="--parse" or action=="--parsefortype":
		print header
		theType=-1
		if action=="--parsefortype":
			theType=int(sys.argv[3])
			
		unknowntags=[]
		for thetag in tags:
			tag=thetag['tag']
			if tag!=theType and theType!=-1:
				continue
			tagdata=thetag['tagdata']
			if not isTagKnown(tag):
				unknowntags.append(tag)
			start=thetag['start']
			fa=thetag['fuzzstart']
			fe=thetag['fuzzend']
			parsedtagdata=parseTag(tag,tagdata,fa,fe)
			if parsedtagdata=="":
				parsedtagdata=repr(tagdata[0:128])
			taglen=thetag['taglen']
			
			print "%05X:%05X:%05X:%d:%s(%d):%d:%s" % (start,fa,fe,tag,getTagName(tag),getTagMinVersion(tag),taglen,repr(parsedtagdata))
		
		if unknowntags!=[]:
			print "unknown tags detected: %s" % repr(uniqlist(unknowntags))
	
#	endtag=True
