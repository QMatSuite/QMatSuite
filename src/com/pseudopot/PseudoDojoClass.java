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

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;
import com.consts.PhysicalConstants;
import com.pseudopot.PseudoDojoEnum.*;

import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class PseudoDojoClass extends PseudoPotential{

	private EnumFunctional typeFunctional;
	private String precString;
	private boolean isRelativ;//whether or not fully relativistic
	
	public PseudoDojoClass() {
		super(EnumPseudoPotLib.PSEUDODOJO, true);
		precisionList.add("Standard");precisionList.add("Stringent");
		functionalList.add(EnumFunctional.PBE);
		functionalList.add(EnumFunctional.PBESOL);
		functionalList.add(EnumFunctional.LDA);
		libFolderName="pseudo_dojo_ONCVPSP_v0.4";
	}
	
	@Override
	public Double getEcutWfc(String element) {
		//use the "normal" hint
		Double out = getDouble(element, "getNormalCut");
		if(out==null || out<0) return null;
		return out * PhysicalConstants.hartreeInRy;//convert Ha to Ry
	}
	@Override
	public Double getDual(String element) {
		return 4.0;
	}
	@Override
	public String getPpType(String element) {
		return EnumPP.NCPP.toString()+"(NC)";
	}
	@Override
	public String getFunctionalType(String element) {
		if(typeFunctional==null) return null;
		return typeFunctional.toString();
	}
	@Override
	protected <T> T getValue(String element, String methodName, Class<T> clazz) { //element name in the format of e.g. "He" 
		//use reflection to simplify code
		
		if (typeFunctional==null || !functionalList.contains(typeFunctional)) return null;
		if (precString==null || !precisionList.contains(precString)) return null;
		
		Method method;
		try {
			switch(typeFunctional) {
				case PBE:
					if (precString.equals("Standard")) {
						if (isRelativ) {
							FrPbeStandard ef = FrPbeStandard.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
						else {
							SrPbeStandard ef = SrPbeStandard.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
					}
					else if (precString.equals("Stringent")) {
						if (isRelativ) {
							FrPbeStringent ef = FrPbeStringent.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
						else {
							SrPbeStringent ef = SrPbeStringent.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
					}
					else return null;
				case PBESOL:
					if (precString.equals("Standard")) {
						if (isRelativ) {
							FrPbesolStandard ef = FrPbesolStandard.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
						else {
							SrPbesolStandard ef = SrPbesolStandard.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
					}
					else if (precString.equals("Stringent")) {
						if (isRelativ) {
							FrPbesolStringent ef = FrPbesolStringent.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
						else {
							SrPbesolStringent ef = SrPbesolStringent.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}	
					}
					else return null;
				case LDA:
					if (precString.equals("Standard")) {
						if (isRelativ) {return null;}
						else {
							SrPwStandard ef = SrPwStandard.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
					}
					else if (precString.equals("Stringent")) {
						if (isRelativ) {return null;}
						else {
							SrPwStringent ef = SrPwStringent.valueOf(element);
							method = ef.getClass().getMethod(methodName);
							return clazz.cast(method.invoke(ef));}
					}
					else return null;
				default:return null;
			}
		}
		catch (IllegalAccessException | InvocationTargetException | SecurityException | NoSuchMethodException e) {
			Alert alert = new Alert(AlertType.INFORMATION);
	    	alert.setTitle("Error");
	    	alert.setContentText("Error in PseudoDojoClass.getString()! "+e.getMessage());
	    	alert.showAndWait();
	    	
			return null;
		}
		catch (IllegalArgumentException e) {
			//cannot find the corresponding item in the enum
			//normal
			return null;
		}
	}
	public EnumFunctional getTypeFunctional() {
		return typeFunctional;
	}

	public void setTypeFunctional(EnumFunctional tf) {
		this.typeFunctional = tf;
	}

	public String getPrecString() {
		return precString;
	}

	public void setPrecString(String tp) {
		//should take null!
		this.precString = tp;
	}

	public boolean isRelativ() {
		return isRelativ;
	}

	public void setRelativ(boolean isRelativ) {
		this.isRelativ = isRelativ;
	}
	
//	public String getFile(String element) { //element name in the format of e.g. "He" 
//	if (typeFunctional==null || !functionalList.contains(typeFunctional)) return null;
//	if (precString==null || !precisionList.contains(precString)) return null;
//	
//	//return getString(element, "getFolderName");
//	
//	try {
//		switch(typeFunctional) {
//			case PBE:
//				if (precString.equals("Standard")) {
//					if (isRelativ) {FrPbeStandard ef = FrPbeStandard.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//					else {SrPbeStandard ef = SrPbeStandard.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//				}
//				else if (precString.equals("Stringent")) {
//					if (isRelativ) {FrPbeStringent ef = FrPbeStringent.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//					else {SrPbeStringent ef = SrPbeStringent.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//				}
//				else return null;
//			case PBESOL:
//				if (precString.equals("Standard")) {
//					if (isRelativ) {FrPbesolStandard ef = FrPbesolStandard.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//					else {SrPbesolStandard ef = SrPbesolStandard.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//				}
//				else if (precString.equals("Stringent")) {
//					if (isRelativ) {FrPbesolStringent ef = FrPbesolStringent.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//					else {SrPbesolStringent ef = SrPbesolStringent.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//				}
//				else return null;
//			case LDA:
//				if (precString.equals("Standard")) {
//					if (isRelativ) {return null;}
//					else {SrPwStandard ef = SrPwStandard.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//				}
//				else if (precString.equals("Stringent")) {
//					if (isRelativ) {return null;}
//					else {SrPwStringent ef = SrPwStringent.valueOf(element);
//					return ef.getFolderName()+File.separator+ef.getFileName();}
//				}
//				else return null;
//			default:return null;
//		}
//	}
//	catch (IllegalArgumentException iae) {
//		return null;
//	}
//
//}

}
