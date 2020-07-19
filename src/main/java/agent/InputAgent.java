/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package agent;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.Objects;

public abstract class InputAgent implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = -76527194192811401L;
	
	
	public Object deepCopy() {//*****is this working as expected?
		try {
			ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
			ObjectOutputStream outputStrm = new ObjectOutputStream(outputStream);
			outputStrm.writeObject(this);
			ByteArrayInputStream inputStream = new ByteArrayInputStream(outputStream.toByteArray());
			ObjectInputStream objInputStream = new ObjectInputStream(inputStream);
			return objInputStream.readObject();
		}
		catch (Exception e) {
			e.printStackTrace();
			return null;
		}
		
	}
	public abstract boolean convertInfoFromInput(String inputStr);
	public String getParameterValue(String paraStr, String inputStr) {
		//1. inputStr can be a line inside an input file
		//or can be a string of the whole input file
		//2. paraStr is the name of the parameter
		if(paraStr==null || paraStr.isEmpty() || inputStr==null) {return null;}
		
		//somehow cannot use \\s+ here
		//Adding an empty space " " to the beginning solves the problem if the parameter is right at the beginning
		//the parameter needs to be followed with "=" with only possible whitespaces in between ("B   =1" is allowed)
		//the parameter must not have preceeding alphabetic character (e.g. tell "cellAB=0" apart from "B=1")
		String[] splitted0 = (" "+inputStr).split("[^a-zA-Z0-9]"+paraStr+"\\s*=");
		//String[] splitted0 = inputStr.split("[^a-zA-Z0-9]?B\\s*=");
		if(splitted0.length<=1) {return null;}//not found
		
		
		
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", splitted0[1]);
		
//		String[] splitted1 = splitted0[1].split("\\R",2);//array is always non-empty
//		if(splitted1.length==0) {return null;}
//		
//		String[] splitted2 = splitted1[0].split(",");
//		if(splitted2.length==0) {return null;}
		
//		return splitted1[0];
		
		return splitted0[1].split("\\R",2)[0].split(",")[0].trim();
	}
	public boolean setParameterValue(String paraStr, String inputStr, WrapperDouble wdVal) {
		//return true: different and set
		Double tmp = null;
		try {
			String strTmp = getParameterValue(paraStr,inputStr);
			if(strTmp==null) {return false;}//when getParameterValue(paraStr,inputStr)==null -> keyword not found
			tmp = Double.valueOf(strTmp);
		}
		catch(IllegalArgumentException e) {
			tmp=null;
		}
		if(Objects.equals(wdVal.getValue(), tmp)) {
			return false;
		}
		else {
			wdVal.setValue(tmp);return true;
		}
	}
	public boolean setParameterValue(String paraStr, String inputStr, WrapperInteger wiVal) {
		//return true: different and set
		Integer tmp = null;
		try {
			String strTmp = getParameterValue(paraStr,inputStr);
			if(strTmp==null) {return false;}//when getParameterValue(paraStr,inputStr)==null -> keyword not found
			tmp = Integer.valueOf(strTmp);
		}
		catch(IllegalArgumentException e) {
			tmp=null;
		}
		
		if(Objects.equals(wiVal.getValue(), tmp)) {
			return false;
		}
		else {
			wiVal.setValue(tmp);return true;
		}
	}
	public String genAgentSummary() {return "";} 
}
