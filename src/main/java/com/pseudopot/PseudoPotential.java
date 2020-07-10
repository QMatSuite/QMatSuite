/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package com.pseudopot;

import java.io.File;
import java.util.ArrayList;

import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;

public abstract class PseudoPotential {
	protected static File rootFolder;
	protected EnumPseudoPotLib libName;
	protected ArrayList<EnumFunctional> functionalList;//functional list
	protected ArrayList<EnumPP> ppList;//pseudopotential type list
	protected ArrayList<String> precisionList;//precision settings
	private boolean fullRelativSupport;
	protected String libFolderName;
	
	static 
    {
		rootFolder = null;
    }
	
	public PseudoPotential(EnumPseudoPotLib ln, boolean fr) {
		libName = ln;
		functionalList = new ArrayList<EnumFunctional>();
		ppList = new ArrayList<EnumPP>();
		precisionList = new ArrayList<String>();
		fullRelativSupport = fr;
		libFolderName="";
	}
	public boolean checkLibraryExistence() {
		if(rootFolder==null || libFolderName==null) return false;
		File fl = new File(rootFolder,libFolderName);
		return fl.canRead();
	}
	public File getRootFolder() {
		return rootFolder;
	}
	public static void setRootFolder(File rt) {
		rootFolder = rt;
	}
	public ArrayList<EnumFunctional> getFunctionalList(){
		return functionalList;
	}
	public ArrayList<EnumPP> getPpList(){
		return ppList;
	}
	public ArrayList<String> getPrecisionList(){
		return precisionList;
	}
	public boolean getFullRelativSupport() {
		return fullRelativSupport;
	}
	
	//methods that should be implemented
	public String getFolder(String element) {
		String st1 =  getString(element, "getFolderName");
		
		if(st1!=null) {
			return libFolderName+File.separator+st1;
		}
		else {return null;}
	}
	public String getFile(String element) { //element name in the format of e.g. "He" 
		
		String st1 =  getString(element, "getFolderName");
		String st2 =  getString(element, "getFileName");
		
		if(st1!=null && st2!=null) {
			return libFolderName+File.separator+st1+File.separator+st2;
		}
		else {return null;}
	}
	protected String getString(String element, String methodName) {
		return getValue(element, methodName, String.class);
	}
	protected Double getDouble(String element, String methodName) {
		return getValue(element, methodName, Double.class);
	}
	protected abstract <T> T getValue(String element, String methodName, Class<T> clazz);
	public abstract Double getEcutWfc(String element);
	public abstract Double getDual(String element);//get ecutrho/ecutwfc, usually 4 for NCPP and higher for USPP
	public abstract String getPpType(String element);
	public abstract String getFunctionalType(String element);
}
