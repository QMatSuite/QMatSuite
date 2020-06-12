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
package main.java.input;

import main.java.com.error.InvalidTypeException;

public class InputValueBoolean extends InputValue {
	/**
	 * 
	 */
	private static final long serialVersionUID = 1372244252110504167L;
	private final Boolean paraDefault;
	private Boolean paraNow = null;//only show up in generating input from agent
	
	public InputValueBoolean(String name, Boolean para, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = para;
		paraNow = paraDefault;
	}
	public InputValueBoolean(String name, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = null;
		paraNow = paraDefault;
		
	}
	public InputValueBoolean(String name) {
		super(name, true);
		paraDefault = null;
		paraNow = paraDefault;
	}
	
	@Override
	public void setValueNow(Integer valueNow) throws InvalidTypeException {
		//will not be null here, otherwise compiler error
		if (!valueNow.equals(1) && !valueNow.equals(0)) {
			throw new InvalidTypeException("cannot convert from int to bool for int="+valueNow);
		}
		paraNow = (valueNow == 1);
	}
	
	@Override
	public void setValueNow(Double valueNow) throws InvalidTypeException{
		throw new InvalidTypeException("cannot convert from double to bool");
	}
	
	@Override
	public void setValueNow(String valueNow) throws InvalidTypeException{	
		throw new InvalidTypeException("cannot convert from string to bool");
	}
	
	@Override
	public void setValueNow(Boolean valueNow) throws InvalidTypeException{	
		paraNow = valueNow;
	}
	
	@Override
	public void setValueNow() throws InvalidTypeException{
		paraNow = null;
	}
	
	public Boolean getValueNow() {
		return paraNow;
	}
	
	@Override
	public String toString(boolean debugbool) {
		if(debugbool) {
			return nameString+", "+paraDefault+", "+paraNow+", "+(boolRequired? "required":"optional")+", "+(explicitWrite? "write":"ignored");
			}
		else {			
			if (paraNow!=null) {
				String strTmp = (paraNow?".true.":".false.");
				return "body".equals(nameString)? ""+strTmp :nameString+"="+strTmp;
			}
			else return null;
		}
	}

}
