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
package input;

import com.error.InvalidTypeException;

public class InputValueString extends InputValue {
	/**
	 * 
	 */
	private static final long serialVersionUID = 2924455053168830612L;
	private final String paraDefault;
	private String paraNow = null;
	
	public InputValueString(String name, String para, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = para;
		paraNow = paraDefault;
		explicitWrite = boolRequired;
	}
	public InputValueString(String name, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = null;
		paraNow = null;
		explicitWrite = boolRequired;
	}
	public InputValueString(String name) {
		super(name, true);
		paraDefault = null;
		paraNow = null;
		explicitWrite = true;
	}
	public boolean isEmpty() {
		if(paraNow==null||paraNow.isEmpty()) return true;
		else return false;
	}

	@Override
	public void print() {
		System.out.println(toString());
	}
	
	@Override
	public void setValueNow(String valueNow) throws InvalidTypeException{
		explicitWrite = boolRequired || (paraDefault != valueNow);
		//explicitWrite = boolRequired || (paraDefault==null && valueNow!=null) || (paraDefault!=null && !paraDefault.equals(valueNow));
		paraNow = valueNow;
	}
	
	@Override
	public void setValueNow(Double valueNow) throws InvalidTypeException{
		throw new InvalidTypeException("cannot convert from double to string");
	}
	
	@Override
	public void setValueNow(Integer valueNow) throws InvalidTypeException{
		throw new InvalidTypeException("cannot convert from integer to string");
	}
	
	@Override
	public void setValueNow(Boolean valueNow) throws InvalidTypeException{
		throw new InvalidTypeException("cannot convert from boolean to string");
	}
	
	@Override
	public void setValueNow() throws InvalidTypeException{
		explicitWrite = boolRequired;
		paraNow = null;
	}
	
	public String getValueNow() {
		return paraNow;
	}


	@Override
	public String toString() {
		if(explicitWrite || boolRequired) return toString(false);
		else return "";
	}
	
	public String toString(boolean debugbool) {
		if(debugbool) {
			return nameString+", "+paraDefault+", "+paraNow+", "+(boolRequired? "required":"optional")+", "+(explicitWrite? "write":"ignored");
			}
		else {
			if (paraNow!=null && !paraNow.isEmpty()) return nameString.equals("body")? ""+paraNow+"" :nameString+"='"+paraNow+"'";
			else return null;
		}
	}

}
