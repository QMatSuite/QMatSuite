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

public class InputValueInt extends InputValue {
	/**
	 * 
	 */
	private static final long serialVersionUID = 8421184057694098619L;
	private final Integer paraDefault;
	private Integer paraNow = null;
	
	public InputValueInt(String name, Integer para, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = para;
		paraNow = paraDefault;
		explicitWrite = boolRequired;
	}
	public InputValueInt(String name, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = null;
		paraNow = null;
		explicitWrite = boolRequired;
	}
	public InputValueInt(String name) {
		super(name, true);
		paraDefault = null;
		paraNow = null;
		explicitWrite = true;
	}

	@Override
	public void print() {
		System.out.println(toString());
	}
	
	@Override
	public void setValueNow(Integer valueNow) throws InvalidTypeException{
		explicitWrite = boolRequired || (paraDefault != valueNow);
		//explicitWrite = boolRequired || (paraDefault==null && valueNow!=null) || (paraDefault!=null && !paraDefault.equals(valueNow));
		paraNow = valueNow;
	}
	
	@Override
	public void setValueNow(Double valueNow) throws InvalidTypeException{
		Integer valueNew = valueNow.intValue();
		//explicitWrite = boolRequired || (paraDefault==null && valueNew!=null) || (paraDefault!=null && !paraDefault.equals(valueNew));
		explicitWrite = boolRequired || (paraDefault != valueNew);
		paraNow = valueNew;
	}
	
	@Override
	public void setValueNow(String valueNow) throws InvalidTypeException{	
		throw new InvalidTypeException("cannot convert from string to int");
	}
	
	@Override
	public void setValueNow(Boolean valueNow) throws InvalidTypeException{
		throw new InvalidTypeException("cannot convert from bool to int");
	}
	
	@Override
	public void setValueNow() throws InvalidTypeException{
		explicitWrite = boolRequired;
		paraNow = null;
	}
	
	public Integer getValueNow() {
		return paraNow;
	}
	
	@Override
	public String toString() {
		return toString(false);
	}
	
	public String toString(boolean debugbool) {
		if(debugbool) {
			return nameString+", "+paraDefault+", "+paraNow+", "+(boolRequired? "required":"optional")+", "+(explicitWrite? "write":"ignored");
			}
		else {
			if (paraNow!=null) return nameString=="body"? ""+paraNow :nameString+"="+paraNow;
			else return "";
		}
	}

}
