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
import com.pseudopot.SSSPEnum.Efficiency;
import com.pseudopot.SSSPEnum.Precision;

import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class SSSPClass extends PseudoPotential{

	private String precString = "Efficiency";
	
	public SSSPClass() {
		super(EnumPseudoPotLib.SSSP, false);
		precisionList.add("Efficiency");precisionList.add("Precision");
		functionalList.add(EnumFunctional.PBE);
	}
	@Override
	public Double getEcutWfc(String element) {
		Double out = getDouble(element, "getEcutwfc");
		if(out==null || out<0) return null;
		return out;//already in Ry
	}
	@Override
	public Double getDual(String element) {
		Double out = getDouble(element, "getDual");
		if(out==null || out<0) return null;
		return out;
	}
	@Override
	public String getPpType(String element) {
		String out = getString(element, "getPpType");
		if(out==null || out.isEmpty()) return null;
		if(out.contains("SG15")) {out+="(NC)";}
		else if (out.contains("GBRV")) {out+="(US)";}
		else if (out.contains("US")) {out+="(US)";}
		else if (out.contains("PAW")) {out+="(PAW)";}
		else if (out.contains("Dojo")) {out+="(NC)";}
		return out;
	}
	@Override
	public String getFunctionalType(String element) {
		return EnumFunctional.PBE.toString();
	}
	@Override
	protected <T> T getValue(String element, String methodName, Class<T> clazz) { //element name in the format of e.g. "He" 
		//use reflection to simplify code
		
		if (precString==null || !precisionList.contains(precString)) return null;
		
		Method method;
		try {
			if (precString.equals("Efficiency")) {
				Efficiency ef = Efficiency.valueOf(element);
				method = ef.getClass().getMethod(methodName);
				return clazz.cast(method.invoke(ef));
			}
			else if (precString.equals("Precision")) {
				Precision ef = Precision.valueOf(element);
				method = ef.getClass().getMethod(methodName);
				return clazz.cast(method.invoke(ef));
			}
			else return null;
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

	public String getPrecString() {
		return precString;
	}

	public void setPrecString(String ps) {
		//need to take null!!
		precString = ps;
	}
//	@Override
//	public String getFile(String element) { //element name in the format of e.g. "He" 
//		if (precString==null || !precisionList.contains(precString)) return null;
//		if (precString.equals("Efficiency")) {
//			try {
//				Efficiency ef = Efficiency.valueOf(element);
//				return ef.getFolderName()+File.separator+ef.getFileName();
//			}
//			catch (IllegalArgumentException iae) {
//				return null;
//			}
//		}
//		else if (precString.equals("Precision")) {
//			try {
//				Precision ef = Precision.valueOf(element);
//				return ef.getFolderName()+File.separator+ef.getFileName();
//			}
//			catch (IllegalArgumentException iae) {
//				return null;
//			}
//		}
//		else return null;
//	}
	
}
