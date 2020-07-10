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
import com.error.ShowAlert;
import com.pseudopot.PSLibraryEnum.PsLibraryV1p0;
import javafx.scene.control.Alert.AlertType;


public class PSLibraryClass extends PseudoPotential{

	private String precString = "high";
	private EnumPP typePP;
	private EnumFunctional typeFunctional;
	private boolean isRelativ;//whether or not fully relativistic

	
	public PSLibraryClass() {
		super(EnumPseudoPotLib.PSLIBRARY, true);
		precisionList.add("low");precisionList.add("high");
		functionalList.add(EnumFunctional.PBE);
		functionalList.add(EnumFunctional.PBESOL);
		functionalList.add(EnumFunctional.LDA);
		ppList.add(EnumPP.PAW);
		ppList.add(EnumPP.USPP);
		libFolderName="PSlibrary_v1.0.0";
	}

	public String getPrecString() {
		return precString;
	}
	
	public void setPrecString(String st) {
		if(!"high".equals(st) && !"low".equals(st)) {
			//ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Try to set not allowed value for precString in PSLibraryClass"+st);
			return;
		}
		precString = st;
	}

	public EnumPP getTypePP() {
		return typePP;
	}

	public void setTypePP(EnumPP typePP) {
		this.typePP = typePP;
	}

	public EnumFunctional getTypeFunctional() {
		return typeFunctional;
	}

	public void setTypeFunctional(EnumFunctional typeFunctional) {
		this.typeFunctional = typeFunctional;
	}

	public boolean isRelativ() {
		return isRelativ;
	}

	public void setRelativ(boolean isRelativ) {
		this.isRelativ = isRelativ;
	}

	@Override
	public String getFolder(String element) {
		return libFolderName;
	}
	@Override
	public String getFile(String element) { //element name in the format of e.g. "He" 
		PsLibraryV1p0 psElem = getPsElement(element);
		if(psElem==null) return null;
		return libFolderName+File.separator+psElem.getFileName();
	}
	private PsLibraryV1p0 getPsElement(String element) { //element name in the format of e.g. "He" 
			if(!this.checkLibraryExistence()) {return null;}
			//ShowAlert.showAlert(AlertType.INFORMATION, "debug", element);
			Integer elemCount = 0;
			ArrayList<PsLibraryV1p0> elementList = new ArrayList<PsLibraryV1p0>();
			
			while(elemCount<1000) {//same as but better than while(true) to prevent infinite loop
				elemCount++;
				try {
					PsLibraryV1p0 psElem = PsLibraryV1p0.valueOf(element+elemCount.toString());
					//functional
					if(EnumFunctional.PBE.equals(typeFunctional)!=
							("pbe".equals(psElem.getFunctionalType()))){continue;}
					if(EnumFunctional.PBESOL.equals(typeFunctional)!=
							("pbesol".equals(psElem.getFunctionalType()))){continue;}
					if(EnumFunctional.LDA.equals(typeFunctional)!=
							("pz".equals(psElem.getFunctionalType()))){continue;}
					//pptype
					if(EnumPP.PAW.equals(typePP)!=("paw".equals(psElem.getPpType()))) {continue;}
					if(EnumPP.USPP.equals(typePP)!=("uspp".equals(psElem.getPpType()))) {continue;}
					//with "l" or not
					if("low".equals(precString) != psElem.isLow()) {continue;}
					//relativ
					if(isRelativ != psElem.isRelativ()) {continue;}
					
					elementList.add(psElem);
				}
				catch(Exception e) {
					break;
				}
			}
			if(elementList.size()==1) {return elementList.get(0);}
			else if(elementList.size()==0){
				//ShowAlert.showAlert(AlertType.INFORMATION, "Error", "In PSLibrary, no file found with the cirteria for element: "+element);
				return null;
			}
			else if(elementList.size()==2){
				if(elementList.get(0).getEcutrho() == elementList.get(1).getEcutrho()) {
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
							"In PSLibrary, two files with same ecutrho found for element "+element);return null;}
				else if(elementList.get(0).getEcutrho() > elementList.get(1).getEcutrho()) {
					if("low".equals(precString)) {return elementList.get(1);}
					else if("high".equals(precString)) {return elementList.get(0);}
					else {ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
							"In PSLibrary, unexpected precString "+precString+" for element: "+element);return null;}
				}
				else {
					if("low".equals(precString)) {return elementList.get(0);}
					else if("high".equals(precString)) {return elementList.get(1);}
					else {ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
							"In PSLibrary, unexpected precString "+precString+" for element: "+element);return null;}
				}
			}
			else {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"In PSLibrary, too many files ("+Integer.toString(elementList.size())+
						") found with the specified criteria for element: "+element);
				return null;
			}
//			File filesList[] = (new File(rootFolder,this.libFolderName)).listFiles();
//			ArrayList<String> fileListElement = new ArrayList<String>();
//			
//			for(File file : filesList) {
//				if(file.getName().contains(element)) {
//					//relativistic
//					if(isRelativ != file.getName().contains("rel")) {continue;}
//					//functional
//					if(EnumFunctional.PBE.equals(typeFunctional)!=
//							(file.getName().contains("pbe") && !file.getName().contains("pbesol"))){continue;}
//					if(EnumFunctional.PBESOL.equals(typeFunctional)!=file.getName().contains("pbesol")) {continue;}
//					if(EnumFunctional.LDA.equals(typeFunctional)!=file.getName().contains("pz")) {continue;}
//					//pptype
//					if(EnumPP.PAW.equals(typePP)!=file.getName().contains("paw")) {continue;}
//					if(EnumPP.USPP.equals(typePP)!=file.getName().contains("rrkjus")) {continue;}
//					//with "l" or not
//					int indEnd = file.getName().lastIndexOf("-");
//					int indSt = file.getName().substring(0, indEnd).lastIndexOf("-");
//					String strTmp = file.getName().substring(indSt+1, indEnd);
//					if(strTmp.contains("l")) {
//						ShowAlert.showAlert(AlertType.INFORMATION, "Debug", 
//								"In PSLibrary, with l: "+file.getName());
//					}
//					if(strTmp.contains("l") != "low".equals(precString)) {continue;}
//					
//					fileListElement.add(file.getName());
//				}
//			}
//			
//			if(fileListElement.size()==1) {return libFolderName+File.separator+fileListElement.get(0);}
//			else if(fileListElement.size()==0){
//				ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
//						"In PSLibrary, no file found with the cirteria for element: "+element);
//				return null;
//			}
//			else if(fileListElement.size()==2){
//				if()
//			}
//			else {
//				ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
//						"In PSLibrary, too many files ("+Integer.toString(fileListElement.size())+
//						") found with the cirteria for element: "+element);
//				return null;
//			}

	}
	
	@Override
	protected <T> T getValue(String element, String methodName, Class<T> clazz) {
		return null;
	}

	@Override
	public Double getEcutWfc(String element) {
		PsLibraryV1p0 psElem = getPsElement(element);
		if(psElem==null) return null;
		return psElem.getEcutwfc();
	}

	@Override
	public Double getDual(String element) {
		PsLibraryV1p0 psElem = getPsElement(element);
		if(psElem==null) return null;
		return psElem.getDual();
	}
	

	@Override
	public String getPpType(String element) {
		if(typePP==null) return null;
		return typePP.toString();
	}

	@Override
	public String getFunctionalType(String element) {
		if(typeFunctional==null) return null;
		return typeFunctional.toString();
	}
	
	
}
