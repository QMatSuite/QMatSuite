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

import com.consts.Constants.EnumInProgram;

public class WrapperEnum extends WrapperClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = -5526687023913245151L;
	private EnumInProgram value;
	final private EnumInProgram defaultValue;
	
	public WrapperEnum(EnumInProgram val) {
		defaultValue = val;
		value = val;
		enabled = false;
	}
	public WrapperEnum(EnumInProgram val,Boolean bl) {
		defaultValue = val;
		value = val;
		enabled = bl;
	}
	public EnumInProgram getValue() {
		return value;
	}
	public void setValue(EnumInProgram val) {
		value = val;
	}
	public Boolean equals(EnumInProgram vl) {
		return java.util.Objects.equals(vl, value);
	}
	@Override
	public Boolean isNull() {
		return value==null;
	}
	public EnumInProgram resetDefault() {
		value = defaultValue;
		return defaultValue;
	}
	@Override
	public Boolean isDefaultNull() {
		return defaultValue==null;
	}
}